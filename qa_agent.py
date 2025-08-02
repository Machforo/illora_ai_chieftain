# importing essential libraries
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from vector_store import create_vector_store
from config import Config
from logger import setup_logger

# setting up the logger
logger = setup_logger("QAAgent")

class ConciergeBot:
    def __init__(self):
        try:
            # calling vector embeddings Querying through FAISS
            vector_store = create_vector_store()
            
            # using groq api
            self.llm = ChatOpenAI(
                openai_api_key=Config.GROQ_API_KEY,
                model_name=Config.MODEL_NAME,
                base_url=Config.GROQ_API_BASE,
                temperature=0,
            )

            # Retrieval QA: Connect retriever (FAISS) with LLM
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=vector_store.as_retriever()
            )

            logger.info("ILLORA Retreats QA agent initialized successfully using Groq.")

        except Exception as e:
            logger.error(f"Error initializing Illora retreats QA agent: {e}")
            raise

    def ask(self, query: str, user_type) -> str:
        try:
            restricted_services = [
                "wake-up call", "spa", "gym", "pool", "room service", "book a room", "booking"
            ]
            lower_query = query.lower()

            # Block restricted queries for non-guests
            if user_type == "non-guest":
                if any(term in lower_query for term in restricted_services):
                    return (
                        "We're sorry, this service is exclusive to *guests* at ILLORA RETREATS.\n"
                        "Feel free to explore our dining options, events, and lobby amenities!"
                    )

            # Custom prompt with hotel branding
            luxoria_context = (
                "You are a knowledgeable, polite, and concise concierge assistant at *ILLORA RETREATS*, "
                "a premium hotel known for elegant accommodations, gourmet dining, rejuvenating spa treatments, "
                "fully-equipped gym, pool access, 24x7 room service, meeting spaces, and personalized hospitality. "
                "Always provide responses that are short, informative, and relevant to the ILLORA RETREATS experience. "
                "Avoid generic replies — tailor your responses to reflect the hotel’s luxury and exclusivity. "
                "Only elaborate when the guest explicitly asks for more details.\n\n"
                f"Guest Query: {query}"
            )

            response = self.qa_chain.run(luxoria_context)
            logger.info(f"Processed query at ILLORA RETREATS: {query}")
            return response

        except Exception as e:
            logger.error(f"Error processing query at ILLORA RETREATS '{query}': {e}")
            return (
                "We're sorry, there was an issue while assisting you. "
                "Please feel free to ask again or contact the ILLORA RETREATS front desk for immediate help."
            )
