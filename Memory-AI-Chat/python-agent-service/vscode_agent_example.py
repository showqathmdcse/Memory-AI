"""
Example usage of the VS Code LangChain Agent

This script demonstrates how to use the VS Code agent service
both directly and via API calls.
"""

import asyncio
import httpx
import json


async def test_direct_usage():
    """Test the VS Code agent service directly."""
    print("\n" + "="*80)
    print("DIRECT USAGE EXAMPLE")
    print("="*80)
    
    from vscode_agent_service import vscode_agent_service
    
    # Example queries
    queries = [
        "List all Python files in the current directory",
        "Read the file vscode_agent_service.py and summarize its purpose",
        "Create a new file called test.txt with content 'Hello from VS Code Agent'",
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"User: {query}")
        
        try:
            response = await vscode_agent_service.execute_task(
                user_query=query,
                execution_id=f"example_session_{i}"
            )
            print(f"Agent: {response}")
        except Exception as e:
            print(f"Error: {e}")


async def test_api_usage():
    """Test the VS Code agent via API calls."""
    print("\n" + "="*80)
    print("API USAGE EXAMPLE")
    print("="*80)
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # Test 1: List available tools
        print("\n--- Available Tools ---")
        try:
            response = await client.get(f"{base_url}/vscode/tools")
            if response.status_code == 200:
                tools_data = response.json()
                print(f"Total tools: {tools_data['tools_count']}")
                for tool in tools_data['tools']:
                    print(f"  - {tool['name']}: {tool['description'][:80]}...")
            else:
                print(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error connecting to API: {e}")
            return
        
        # Test 2: Execute a task
        print("\n--- Execute Task ---")
        task_request = {
            "query": "List all files in the current directory",
            "execution_id": "api_test_session"
        }
        
        try:
            response = await client.post(
                f"{base_url}/vscode/execute",
                json=task_request
            )
            if response.status_code == 200:
                result = response.json()
                print(f"Execution ID: {result['execution_id']}")
                print(f"Response: {result['response'][:200]}...")
            else:
                print(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 3: Execute another task with the same session
        print("\n--- Execute Follow-up Task ---")
        task_request = {
            "query": "How many Python files did you find?",
            "execution_id": "api_test_session"  # Same session for context
        }
        
        try:
            response = await client.post(
                f"{base_url}/vscode/execute",
                json=task_request
            )
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {result['response']}")
            else:
                print(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 4: Clear session memory
        print("\n--- Clear Session Memory ---")
        try:
            response = await client.delete(
                f"{base_url}/vscode/memory/api_test_session"
            )
            if response.status_code == 200:
                print(response.json()['message'])
            else:
                print(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Run all examples."""
    print("\n" + "="*80)
    print("VS CODE LANGCHAIN AGENT - EXAMPLE USAGE")
    print("="*80)
    
    # Test direct usage
    await test_direct_usage()
    
    # Test API usage (requires server to be running)
    print("\n\nNote: The following API tests require the FastAPI server to be running.")
    print("Start the server with: python main.py")
    input("\nPress Enter to continue with API tests (or Ctrl+C to skip)...")
    
    await test_api_usage()
    
    print("\n" + "="*80)
    print("EXAMPLES COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
