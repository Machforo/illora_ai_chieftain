from app.agents.qa_agent import ConciergeBot

def run_cli():
    print("🛎️  Welcome to AI Chieftain – Hotel Concierge Bot")
    print("Type 'exit' to quit.\n")

    bot = ConciergeBot()

    while True:
        query = input("You: ")
        if query.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        response = bot.ask(query)
        print("Bot:", response)
