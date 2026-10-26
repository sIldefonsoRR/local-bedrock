import boto3
import json

# 📌 Default endpoints and credentials
DEFAULT_BEDROCK_ENDPOINT = "http://localhost:4566"
DEFAULT_REGION = "us-east-1"
DEFAULT_ACCESS_KEY = "fake"
DEFAULT_SECRET_KEY = "fake"

# 📌 Default model ID for the Bedrock API
DEFAULT_MODEL_ID = "amazon.titan-text-express-v1"


def create_bedrock_client():
    """
    Create a Bedrock Runtime Client pointed at fakecloud
    """
    # 📌 Create a Bedrock Runtime Client pointed at fakecloud
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=DEFAULT_REGION,
        endpoint_url=DEFAULT_BEDROCK_ENDPOINT,
        aws_access_key_id=DEFAULT_ACCESS_KEY,
        aws_secret_access_key=DEFAULT_SECRET_KEY
    )


def call_bedrock_llm(bedrock_client, prompt, model_id=DEFAULT_MODEL_ID):
    """
    Call the Bedrock API and return the response text
    Args:
        bedrock_client: The Bedrock Runtime Client
        prompt: The prompt to send to the Bedrock API
        model_id: The model ID to use
    Returns:
        (text, is_reply): the model's reply and True, or a diagnostic
        message (empty response, raw JSON, error) and False
    """
    try:
        # 📌 Call the Bedrock API and return the response text
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "temperature": 0.2,
                    "maxTokenCount": 1000
                }
            })
        )

        raw_body = response.get('body').read().decode('utf-8')
        response_body = json.loads(raw_body)

        # 📌 Titan shape: results[].outputText
        results = response_body.get('results', [])
        if results:
            first = results[0]
            text = (first.get('outputText') or '').strip()
            reason = first.get('completionReason', '')
            if text:
                return text, True
            if reason == 'LENGTH':
                return (
                    "Empty response: Model exhausted maxTokenCount in reasoning "
                    f"(tokenCount={first.get('tokenCount')}). "
                    "Increase maxTokenCount or use a model without thinking."
                ), False
            return json.dumps(first, indent=2), False

        # 📌 Other shapes: outputs[].text or {"output": ...}
        outputs = response_body.get('outputs', [])
        if outputs and outputs[0].get('text'):
            return outputs[0].get('text').strip(), True
        if response_body.get('output'):
            return response_body.get('output').strip(), True
        return json.dumps(response_body, indent=2), False

    except Exception as e:
        return f"❌ Error executing script: {e}", False
