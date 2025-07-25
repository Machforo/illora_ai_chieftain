from qa_agent import ConciergeBot


# function to make the agent run on the terminal
def run_cli():
    print(" Welcome to LUXORIA SUITES. How can I assist you?")
    print("Type 'exit' to quit.\n")

    bot = ConciergeBot()

    while True:
        query = input("You: ")
        if query.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        response = bot.ask(query)
        print("Bot:", response)
