import asyncio
policy = asyncio.get_event_loop_policy()
policy.new_event_loop()
