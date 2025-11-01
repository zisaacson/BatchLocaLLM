"""
Test the HuggingFace model parser with real content.
"""

from core.batch_app.model_parser import parse_and_prepare_model

# Example content from HuggingFace model page (Gemma 3 12B Q4_0 GGUF)
test_content = """
How to use from vLLM

Copy

hf auth login
Install from pip

Copy
# Install vLLM from pip:
pip install vllm

Copy
# Load and run the model:
vllm serve "google/gemma-3-12b-it-qat-q4_0-gguf"

Copy
# Call the server using curl:
curl -X POST "http://localhost:8000/v1/chat/completions" \
	-H "Content-Type: application/json" \
	--data '{
		"model": "google/gemma-3-12b-it-qat-q4_0-gguf",
		"messages": [
			{
				"role": "user",
				"content": [
					{
						"type": "text",
						"text": "Describe this image in one sentence."
					},
					{
						"type": "image_url",
						"image_url": {
							"url": "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
						}
					}
				]
			}
		]
	}'
Use Docker images
Quick Links
Read the vLLM documentation
"""

def test_model(content, description):
    """Test parser with a model."""
    print(f"\n{'='*70}")
    print(f"Testing: {description}")
    print('='*70)

    try:
        result = parse_and_prepare_model(content)

        print(f"\n✅ Model ID: {result['model_id']}")
        print(f"📝 Name: {result['name']}")
        print(f"💾 Size: {result['size_gb']} GB")
        print(f"🎯 Estimated Memory: {result['estimated_memory_gb']} GB")
        print(f"🖥️  RTX 4080 Compatible: {'✅ YES' if result['rtx4080_compatible'] else '❌ NO'}")
        print(f"⚙️  CPU Offload Needed: {result['cpu_offload_gb']} GB")

        print(f"\n📋 Recommendations:")
        for rec in result.get('recommendations', []):
            print(f"   {rec}")

        print(f"\n🚀 Optimized vLLM Command:")
        print(f"   {result['vllm_serve_command']}")

        if result['installation_notes']:
            print(f"\n📦 Installation:")
            for line in result['installation_notes'].split('\n'):
                print(f"   {line}")

    except Exception as e:
        print(f"❌ Failed to parse: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🧪 TESTING HUGGINGFACE MODEL PARSER")

    # Test 1: Gemma 3 12B Q4_0 (should fit)
    test_model(test_content, "Gemma 3 12B Q4_0 GGUF")

    # Test 2: OLMo 2 7B FP16 (needs CPU offload)
    olmo_content = """
    vllm serve "allenai/OLMo-2-1124-7B-Instruct"
    pip install vllm
    """
    test_model(olmo_content, "OLMo 2 7B FP16 (unquantized)")

    # Test 3: Simulated 27B model (definitely needs CPU offload)
    gemma_27b_content = """
    vllm serve "google/gemma-3-27b-it"
    hf auth login
    pip install vllm
    """
    test_model(gemma_27b_content, "Gemma 3 27B FP16 (large model)")

    print("\n" + "="*70)
    print("✅ All tests complete!")
    print("="*70)

