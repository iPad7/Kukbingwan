"""
다양한 LLM 모델을 지원하는 팩토리 패턴 구현
지원 모델: Qwen, OpenAI (GPT), Anthropic (Claude), Google (Gemini)
"""
from abc import ABC, abstractmethod
from typing import Optional, Generator

from loguru import logger

import sys
sys.path.append(str(__file__).rsplit("/", 2)[0])
from config import LLMConfig, LLMProvider, config


class BaseLLM(ABC):
    """LLM 기본 인터페이스"""
    
    def __init__(self, llm_config: LLMConfig):
        self.config = llm_config
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """텍스트 생성"""
        pass
    
    @abstractmethod
    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """스트리밍 텍스트 생성"""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """모델 이름 반환"""
        pass


class QwenLLM(BaseLLM):
    """Qwen 모델 (로컬 실행)"""
    
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        self._model = None
        self._tokenizer = None
        self._setup_gpu()
    
    def _setup_gpu(self):
        """GPU 설정"""
        import os
        
        if self.config.gpu_ids is not None:
            os.environ["CUDA_VISIBLE_DEVICES"] = self.config.gpu_ids
            logger.info(f"Using GPU(s): {self.config.gpu_ids}")
    
    def _get_device_map(self):
        """device_map 설정 반환"""
        if self.config.gpu_ids is None:
            return "auto"
        
        gpu_list = [int(g.strip()) for g in self.config.gpu_ids.split(",")]
        
        if len(gpu_list) == 1:
            # 단일 GPU: 해당 GPU에 전체 모델 로드
            return {"": f"cuda:0"}  # CUDA_VISIBLE_DEVICES 설정 후 0번이 됨
        else:
            # 다중 GPU: auto로 분산
            return "auto"
    
    def _load_model(self):
        """모델 지연 로딩"""
        if self._model is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            logger.info(f"Loading Qwen model: {self.config.qwen_model}")
            
            device_map = self._get_device_map()
            logger.info(f"Device map: {device_map}")
            
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.qwen_model,
                trust_remote_code=True,
                cache_dir="/data2/models"
            )
            
            self._model = AutoModelForCausalLM.from_pretrained(
                self.config.qwen_model,
                torch_dtype=torch.bfloat16,
                device_map=device_map,
                trust_remote_code=True,
                cache_dir="/data2/models"
            )
            
            logger.info("Qwen model loaded successfully")
    
    @property
    def model_name(self) -> str:
        return self.config.qwen_model
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        self._load_model()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        text = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)
        
        outputs = self._model.generate(
            **inputs,
            max_new_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            do_sample=True,
            pad_token_id=self._tokenizer.eos_token_id,
        )
        
        generated_ids = outputs[0][inputs["input_ids"].shape[-1]:]
        response = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        return response
    
    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        from transformers import TextIteratorStreamer
        import threading
        
        self._load_model()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        text = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)
        
        streamer = TextIteratorStreamer(self._tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = {
            **inputs,
            "max_new_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "do_sample": True,
            "streamer": streamer,
            "pad_token_id": self._tokenizer.eos_token_id,
        }
        
        thread = threading.Thread(target=self._model.generate, kwargs=generation_kwargs)
        thread.start()
        
        for text in streamer:
            yield text


class OpenAILLM(BaseLLM):
    """OpenAI GPT 모델"""
    
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        
        if not self.config.openai_api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        
        from openai import OpenAI
        self._client = OpenAI(api_key=self.config.openai_api_key)
    
    @property
    def model_name(self) -> str:
        return self.config.openai_model
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self._client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        
        return response.choices[0].message.content
    
    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        stream = self._client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=True,
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicLLM(BaseLLM):
    """Anthropic Claude 모델"""
    
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        
        if not self.config.anthropic_api_key:
            raise ValueError("Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable.")
        
        from anthropic import Anthropic
        self._client = Anthropic(api_key=self.config.anthropic_api_key)
    
    @property
    def model_name(self) -> str:
        return self.config.anthropic_model
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        kwargs = {
            "model": self.config.anthropic_model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = self._client.messages.create(**kwargs)
        
        return response.content[0].text
    
    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        kwargs = {
            "model": self.config.anthropic_model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text


class GoogleLLM(BaseLLM):
    """Google Gemini 모델"""
    
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        
        if not self.config.google_api_key:
            raise ValueError("Google API key not found. Set GOOGLE_API_KEY environment variable.")
        
        import google.generativeai as genai
        genai.configure(api_key=self.config.google_api_key)
        self._model = genai.GenerativeModel(self.config.google_model)
    
    @property
    def model_name(self) -> str:
        return self.config.google_model
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        response = self._model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            }
        )
        
        return response.text
    
    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        response = self._model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            },
            stream=True,
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text


class ModelFactory:
    """LLM 모델 팩토리"""
    
    _providers = {
        LLMProvider.QWEN: QwenLLM,
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.ANTHROPIC: AnthropicLLM,
        LLMProvider.GOOGLE: GoogleLLM,
    }
    
    @classmethod
    def create(
        cls,
        provider: Optional[LLMProvider] = None,
        llm_config: Optional[LLMConfig] = None
    ) -> BaseLLM:
        """LLM 모델 인스턴스 생성"""
        llm_config = llm_config or config.llm
        provider = provider or llm_config.provider
        
        if provider not in cls._providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        logger.info(f"Creating LLM instance: {provider.value}")
        return cls._providers[provider](llm_config)
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """사용 가능한 프로바이더 목록"""
        return [p.value for p in cls._providers.keys()]
    
    @classmethod
    def create_by_name(cls, provider_name: str, llm_config: Optional[LLMConfig] = None) -> BaseLLM:
        """문자열 이름으로 모델 생성"""
        provider = LLMProvider(provider_name.lower())
        return cls.create(provider, llm_config)


if __name__ == "__main__":
    # 사용 예시
    print("Available providers:", ModelFactory.list_providers())
    
    # Qwen 모델 테스트 (로컬 모델이 있는 경우)
    try:
        llm = ModelFactory.create(LLMProvider.QWEN)
        response = llm.generate("안녕하세요, 간단한 테스트입니다.")
        print(f"Qwen response: {response}")
    except Exception as e:
        print(f"Qwen test failed: {e}")

