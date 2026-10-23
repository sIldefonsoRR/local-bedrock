from bedrock import call_bedrock_llm, create_bedrock_client

# 📌 Updated prompt to inject whole conversation context
DEFAULT_PROMPT = (
    "You are a helpful assistant. Respond with a single short sentence (maximum 20 words).\n\n"
    "Conversation History:\n{history}\n"
    "Current Question: {question}\n"
    "Assistant:"
)

# 📌 a. Create a Bedrock Runtime Client
bedrock_client = create_bedrock_client()

# 📌 b. Initialize Session Memory List
session_history = []

# 📌 c. Cycle to receive user input
while True:
    print("\n--------------------------------")
    print("What can I help you with? (or 'exit' to quit)", end="")
    print("\n--------------------------------")
    question = input("\n>>> ")
    if question.lower() == "exit":
        break

    # 📌 1. Format history into a cohesive text block
    history_string = ""
    for turn in session_history:
        history_string += f"User: {turn['user']}\nAssistant: {turn['assistant']}\n"

    # 📌 2. Generate final prompt injecting the history context
    prompt = DEFAULT_PROMPT.format(history=history_string, question=question)

    # 📌 3. Get response from LLM
    response_text, is_reply = call_bedrock_llm(bedrock_client, prompt)

    # Print response to user
    print(f"\n{response_text}")

    # 📌 4. Save current turn to the session history state (real replies only)
    if not is_reply:
        continue
    session_history.append({
        "user": question,
        "assistant": response_text
    })

    # Optional: Prevent prompt from getting too long over time (Keep last 5 turns)
    if len(session_history) > 5:
        session_history.pop(0)
