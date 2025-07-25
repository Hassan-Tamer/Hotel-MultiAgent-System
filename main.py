import asyncio
import uuid
from Hotel_Agent.agent import coordinator_agent
from dotenv import load_dotenv # type: ignore
from google.adk.runners import Runner # type: ignore
from google.adk.sessions import InMemorySessionService # type: ignore
from google.genai import types # type: ignore
from STT import *
from TTS import *
VERBOSE = False

async def display_state(session_service, app_name, user_id, session_id):
    """Display the current state of the session."""
    if not VERBOSE:
        return
    session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
    print("\nCurrent Session State:")
    for key, value in session.state.items():
        print(f"{key}: {value}")
    print("\n" + "=" * 30 + "\n")

async def process_agent_response(event):
    """Process and display agent response events."""

    if VERBOSE:
        print(f"Event ID: {event.id}, Author: {event.author}")

    # Check for specific parts first
    if VERBOSE:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text and not part.text.isspace():
                    print(f"  Text: '{part.text.strip()}'")

    final_response = None
    if event.is_final_response():
        if (
            event.content
            and event.content.parts
            and hasattr(event.content.parts[0], "text")
            and event.content.parts[0].text
        ):
            final_response = event.content.parts[0].text.strip()
            
            # print("==" * 30)
            # print(f"Agent Response: {final_response}")
            # print("==" * 30)

        else:
            print("No final response text found in event content.")

    return final_response

async def call_agent_async(runner, user_id, session_id, query):
    """Call the agent asynchronously with the user's query."""
    content = types.Content(role="user", parts=[types.Part(text=query)])
    
    await display_state(runner.session_service, runner.app_name, user_id, session_id)

    final_response_text = None
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            response = await process_agent_response(event)
            if response:
                final_response_text = response
    except Exception as e:
        print(f"Error during agent call: {e}")

    await display_state(runner.session_service, runner.app_name, user_id, session_id)

    return final_response_text


load_dotenv()
session_service = InMemorySessionService()

rooms_db = {
    "room_101": {"type": "single", "price": 100, "available": True},
    "room_102": {"type": "double", "price": 150, "available": True},
    "room_103": {"type": "suite", "price": 300, "available": False},
    "room_104": {"type": "single", "price": 100, "available": True},
}

initial_state = {
    "user_name": "User", 
    "recent_bookings": [],
    "pending_issues": [],
    "rooms_db": rooms_db,
}

gcp_tts = GCP_TTS()
playai_tts = PlayAI_TTS()
TTS_client = TTSClient(gcp_tts)

gcp_stt = GCP_STT()
groq_stt = GroqWhisper_STT()
STT_client = STTClient(gcp_stt)

async def main_async():
    # Setup constants
    APP_NAME = "Hotel Customer Support"
    USER_ID = str(uuid.uuid4())

    new_session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state=initial_state,
    )
    SESSION_ID = new_session.id
    print(f"Created new session: {SESSION_ID}")

    runner = Runner(
        agent=coordinator_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print("\nWelcome to Customer Service Chat!")
    print("Type 'exit' or 'quit' to end the conversation.\n")

    while True:
        # user_input = input("You: ")
        user_input = STT_client.listen_and_transcribe()
        # user_input = "اهلا، انا اسمي حسن"

        if user_input.lower() in ["exit", "quit"]:
            print("Ending conversation. Goodbye!")
            break

        response = await call_agent_async(runner, USER_ID, SESSION_ID, user_input)
        print(f"Agent: {response}")
        if response:
            TTS_client.speak(response)
            TTS_client.set_strategy(playai_tts)
            TTS_client.speak(response)
            TTS_client.set_strategy(gcp_tts)

    final_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    print("\nFinal Session State:")
    for key, value in final_session.state.items():
        print(f"{key}: {value}")


def main():
    """Entry point for the application."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
