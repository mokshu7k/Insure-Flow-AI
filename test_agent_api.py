"""Quick test script to verify the agent API is working with gemini-1.5-flash"""
import asyncio
import httpx
import json

async def test_agent():
    base_url = "http://localhost:8000"
    
    # First login to get token
    print("[*] Logging in...")
    async with httpx.AsyncClient() as client:
        login_response = await client.post(
            f"{base_url}/api/auth/login",
            json={"email": "customer1@test.ai", "password": "Test1234!"}
        )
        if login_response.status_code != 200:
            print(f"[X] Login failed: {login_response.text}")
            return
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[OK] Login successful")
        
        # Create new session
        print("\n[*] Creating new agent session...")
        session_response = await client.post(
            f"{base_url}/api/agent/sessions",
            headers=headers
        )
        if session_response.status_code != 200:
            print(f"[X] Session creation failed: {session_response.text}")
            return
        
        session_id = session_response.json()["session_id"]
        print(f"[OK] Session created: {session_id}")
        
        # Send test message
        print("\n[*] Sending message: 'What documents are needed for a health claim?'")
        message_response = await client.post(
            f"{base_url}/api/agent/sessions/{session_id}/message",
            headers=headers,
            json={"message": "What documents are needed for a health claim?"}
        )
        
        if message_response.status_code != 200:
            print(f"[X] Message failed: {message_response.text}")
            return
        
        result = message_response.json()
        print(f"\n[OK] Response received:")
        print(f"Reply: {result['reply']}")
        print(f"Intent: {result.get('intent', 'N/A')}")
        
        # Check if it's an error message
        if "having trouble connecting" in result['reply'].lower():
            print("\n[X] Still getting error response!")
        else:
            print("\n[OK] AI assistant is working correctly!")

if __name__ == "__main__":
    asyncio.run(test_agent())
