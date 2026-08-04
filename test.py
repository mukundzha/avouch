import asyncio


async def good():
    await asyncio.sleep(1)


async def bad():
    print("Hello")


async def another_bad():
    x = 10
    return x