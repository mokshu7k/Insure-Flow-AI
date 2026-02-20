import httpx, asyncio

async def test():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as c:
        r = await c.post("/api/auth/register", json={
            "email": "probe@test.com",
            "password": "testpass123",
            "role": "CUSTOMER"
        })
        print("STATUS:", r.status_code)
        print("BODY:", r.text[:1000])

asyncio.run(test())
