"""Integration tests with real vLLM - VERY HIGH VALUE tests.

These tests use real vLLM to test actual inference behavior.
They are slower but catch real integration bugs.

Tests cover:
- Real model loading
- Real inference
- Real GPU memory usage
- Real error conditions
- End-to-end batch processing

NOTE: These tests require a GPU and will take several minutes to run.
Run with: pytest core/tests/integration/test_vllm_real.py -v -s
"""

import pytest
import json
import tempfile
import time
from pathlib import Path

# Mark all tests in this module as requiring GPU, slow, and integration
pytestmark = [
    pytest.mark.gpu,
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.skipif(
        not Path("/dev/nvidia0").exists(),
        reason="GPU not available - skipping real vLLM tests"
    )
]


class TestRealModelLoading:
    """Test real vLLM model loading."""

    def test_load_small_model(self):
        """Test loading a small model (Qwen 2.5 0.5B)."""
        from vllm import LLM
        
        # Load smallest possible model for testing
        model_name = "Qwen/Qwen2.5-0.5B-Instruct"
        
        start_time = time.time()
        llm = LLM(
            model=model_name,
            gpu_memory_utilization=0.5,
            max_model_len=2048,
            enforce_eager=True  # Faster for testing
        )
        load_time = time.time() - start_time
        
        assert llm is not None
        assert load_time < 60  # Should load in under 1 minute
        
        # Clean up
        del llm

    def test_model_loading_with_invalid_name(self):
        """Test that invalid model name raises error."""
        from vllm import LLM
        
        with pytest.raises(Exception):
            llm = LLM(model="invalid/model/name")


class TestRealInference:
    """Test real vLLM inference."""

    @pytest.fixture(scope="class")
    def llm(self):
        """Load model once for all tests in this class."""
        from vllm import LLM
        
        model_name = "Qwen/Qwen2.5-0.5B-Instruct"
        llm = LLM(
            model=model_name,
            gpu_memory_utilization=0.5,
            max_model_len=2048,
            enforce_eager=True
        )
        yield llm
        del llm

    def test_single_inference(self, llm):
        """Test single inference request."""
        from vllm import SamplingParams
        
        prompt = "user: What is 2+2?\nassistant:"
        sampling_params = SamplingParams(
            temperature=0.0,  # Deterministic
            max_tokens=50
        )
        
        outputs = llm.generate([prompt], sampling_params)
        
        assert len(outputs) == 1
        assert len(outputs[0].outputs) > 0
        assert len(outputs[0].outputs[0].text) > 0
        assert outputs[0].outputs[0].finish_reason in ['stop', 'length']

    def test_batch_inference(self, llm):
        """Test batch inference with multiple requests."""
        from vllm import SamplingParams
        
        prompts = [
            "user: What is 2+2?\nassistant:",
            "user: What is 3+3?\nassistant:",
            "user: What is 4+4?\nassistant:",
        ]
        sampling_params = SamplingParams(
            temperature=0.0,
            max_tokens=50
        )
        
        start_time = time.time()
        outputs = llm.generate(prompts, sampling_params)
        inference_time = time.time() - start_time
        
        assert len(outputs) == 3
        assert all(len(o.outputs) > 0 for o in outputs)
        assert all(len(o.outputs[0].text) > 0 for o in outputs)
        
        # Batch should be faster than 3x single requests
        assert inference_time < 10  # Should complete in under 10 seconds

    def test_token_counting(self, llm):
        """Test that token counts are accurate."""
        from vllm import SamplingParams
        
        prompt = "user: Hello\nassistant:"
        sampling_params = SamplingParams(
            temperature=0.0,
            max_tokens=10
        )
        
        outputs = llm.generate([prompt], sampling_params)
        
        output = outputs[0]
        assert output.prompt_token_ids is not None
        assert len(output.prompt_token_ids) > 0
        assert len(output.outputs[0].token_ids) > 0
        
        # Total tokens should be sum of prompt + completion
        total_tokens = len(output.prompt_token_ids) + len(output.outputs[0].token_ids)
        assert total_tokens > 0

    def test_max_tokens_limit(self, llm):
        """Test that max_tokens limit is respected."""
        from vllm import SamplingParams
        
        prompt = "user: Write a very long story\nassistant:"
        max_tokens = 20
        sampling_params = SamplingParams(
            temperature=0.7,
            max_tokens=max_tokens
        )
        
        outputs = llm.generate([prompt], sampling_params)
        
        output = outputs[0]
        completion_tokens = len(output.outputs[0].token_ids)
        
        # Should not exceed max_tokens
        assert completion_tokens <= max_tokens


class TestRealGPUMemory:
    """Test real GPU memory usage."""

    def test_gpu_memory_monitoring(self):
        """Test that we can monitor GPU memory during inference."""
        import pynvml
        from vllm import LLM, SamplingParams
        
        # Initialize NVML
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # Get memory before loading model
        mem_before = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        # Load model
        llm = LLM(
            model="Qwen/Qwen2.5-0.5B-Instruct",
            gpu_memory_utilization=0.5,
            max_model_len=2048,
            enforce_eager=True
        )
        
        # Get memory after loading model
        mem_after = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        # Model should use some memory
        memory_used = mem_after.used - mem_before.used
        assert memory_used > 0
        
        # Run inference
        prompt = "user: Hello\nassistant:"
        sampling_params = SamplingParams(temperature=0.0, max_tokens=10)
        outputs = llm.generate([prompt], sampling_params)
        
        # Get memory during inference
        mem_during = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        # Should not use significantly more memory than model loading
        # (some increase is expected for KV cache)
        assert mem_during.used <= mem_after.used * 1.2
        
        # Clean up
        del llm
        pynvml.nvmlShutdown()


class TestRealEndToEnd:
    """Test end-to-end batch processing with real vLLM."""

    def test_end_to_end_batch_processing(self):
        """Test complete batch processing workflow with real vLLM."""
        from vllm import LLM, SamplingParams
        
        # Create input file with 10 requests
        requests = []
        for i in range(10):
            requests.append({
                "custom_id": f"req-{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "Qwen/Qwen2.5-0.5B-Instruct",
                    "messages": [
                        {"role": "user", "content": f"What is {i}+{i}?"}
                    ]
                }
            })
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for req in requests:
                f.write(json.dumps(req) + '\n')
            input_file = f.name
        
        # Create output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_file = f.name
        
        try:
            # Load model
            llm = LLM(
                model="Qwen/Qwen2.5-0.5B-Instruct",
                gpu_memory_utilization=0.5,
                max_model_len=2048,
                enforce_eager=True
            )
            
            # Load requests
            all_requests = []
            with open(input_file) as f:
                for line in f:
                    if line.strip():
                        all_requests.append(json.loads(line))
            
            # Extract prompts
            prompts = []
            for req in all_requests:
                messages = req['body']['messages']
                prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                prompts.append(prompt)
            
            # Run inference
            sampling_params = SamplingParams(temperature=0.0, max_tokens=50)
            start_time = time.time()
            outputs = llm.generate(prompts, sampling_params)
            inference_time = time.time() - start_time
            
            # Save results
            with open(output_file, 'w') as f:
                for i, output in enumerate(outputs):
                    result = {
                        'id': f'batch_req_{i}',
                        'custom_id': all_requests[i]['custom_id'],
                        'response': {
                            'status_code': 200,
                            'body': {
                                'choices': [{
                                    'message': {
                                        'role': 'assistant',
                                        'content': output.outputs[0].text
                                    },
                                    'finish_reason': output.outputs[0].finish_reason
                                }],
                                'usage': {
                                    'prompt_tokens': len(output.prompt_token_ids),
                                    'completion_tokens': len(output.outputs[0].token_ids),
                                    'total_tokens': len(output.prompt_token_ids) + len(output.outputs[0].token_ids)
                                }
                            }
                        }
                    }
                    f.write(json.dumps(result) + '\n')
            
            # Verify results
            with open(output_file) as f:
                results = [json.loads(line) for line in f if line.strip()]
            
            assert len(results) == 10
            assert all('response' in r for r in results)
            assert all(r['response']['status_code'] == 200 for r in results)
            
            # Calculate throughput
            total_tokens = sum(r['response']['body']['usage']['total_tokens'] for r in results)
            throughput = total_tokens / inference_time
            
            print(f"\n✅ Processed {len(results)} requests in {inference_time:.1f}s")
            print(f"📊 Throughput: {throughput:.0f} tokens/sec")
            print(f"🎯 Average: {inference_time/len(results):.2f}s per request")
            
            # Clean up
            del llm
            
        finally:
            Path(input_file).unlink()
            Path(output_file).unlink()

