import unittest
from unittest.mock import AsyncMock, patch

from foundation_next.mcp_gateway import MCPGateway, ToolError, ToolSpec
from foundation_next.omniguard_client import OmniGuardClient, OmniGuardDecision, OmniGuardResult


def verdict(decision):
    return OmniGuardResult(decision=decision, confidence=1.0, signature="test", latency_ms=1.0, tier_latencies={})


class OmniGuardBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_client_denies_execution(self):
        gateway = MCPGateway(enable_omniguard=False)
        gateway._enable_omniguard = True
        gateway._omniguard = None
        with self.assertRaises(ToolError):
            await gateway.execute(tool="lookup", capability="read", arguments={}, authorization="token")

    async def test_block_denies_execution(self):
        gateway = MCPGateway(enable_omniguard=False)
        gateway._enable_omniguard = True
        gateway._omniguard = AsyncMock()
        gateway._omniguard.inspect.return_value = verdict(OmniGuardDecision.BLOCK)
        executed = []

        async def handler(args):
            executed.append(args)
            return {"status": "success"}

        gateway.register(ToolSpec("lookup", "read"), handler)
        with self.assertRaises(ToolError):
            await gateway.execute(tool="lookup", capability="read", arguments={}, authorization="token")
        self.assertEqual(executed, [])

    async def test_allow_executes_registered_handler(self):
        gateway = MCPGateway(enable_omniguard=False)
        gateway._enable_omniguard = True
        gateway._omniguard = AsyncMock()
        gateway._omniguard.inspect.return_value = verdict(OmniGuardDecision.ALLOW)

        async def handler(args):
            return {"status": "success", "value": args["value"]}

        gateway.register(ToolSpec("lookup", "read"), handler)
        response = await gateway.execute(tool="lookup", capability="read", arguments={"value": 7}, authorization="token")
        self.assertEqual(response["value"], 7)

    async def test_missing_api_key_is_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            client = OmniGuardClient()
            with self.assertRaises(RuntimeError):
                await client.inspect([{"role": "user", "content": "hello"}])
