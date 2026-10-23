from bedrock import call_bedrock_llm, create_bedrock_client

# 📌 Default prompt
DEFAULT_PROMPT = (
    "Respond with a single short sentence (maximum 20 words).\n\n"
    "Question: {question}\n"
)

# 📌 a. Create a Bedrock Runtime Client
bedrock_client = create_bedrock_client()


# 📌 b. Cycle to receive user input
while True:
    print("\n--------------------------------")
    print("What can I help you with? (or 'exit' to quit)", end="")
    print("\n--------------------------------")
    question = input("\n>>> ")
    if question.lower() == "exit":
        break
    prompt = DEFAULT_PROMPT.format(question=question)
    response_text, _ = call_bedrock_llm(bedrock_client, prompt)
    print(response_text)
