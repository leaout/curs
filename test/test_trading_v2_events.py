# coding: utf-8
import unittest

from trading_v2.events import InMemoryEventStream


class TradingV2EventStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_publish_and_subscribe(self) -> None:
        stream = InMemoryEventStream(history_size=10, subscriber_queue_size=2)
        subscription = await stream.subscribe()

        published = await stream.publish("bar.closed", {"symbol": "600000"})
        received = await subscription.get()

        self.assertEqual(received.id, published.id)
        self.assertEqual(received.sequence, 1)
        self.assertEqual(received.payload["symbol"], "600000")

        await subscription.close()
        await stream.close()

    async def test_replay_and_slow_consumer_drop_oldest(self) -> None:
        stream = InMemoryEventStream(history_size=10, subscriber_queue_size=1)
        await stream.publish("event.one")
        await stream.publish("event.two")

        replay = await stream.subscribe(replay=2, queue_size=2)
        self.assertEqual((await replay.get()).topic, "event.one")
        self.assertEqual((await replay.get()).topic, "event.two")

        live = await stream.subscribe(queue_size=1)
        await stream.publish("event.three")
        await stream.publish("event.four")
        self.assertEqual((await live.get()).topic, "event.four")
        self.assertEqual(live.dropped_events, 1)

        await replay.close()
        await live.close()
        await stream.close()

    async def test_recent_history_is_bounded(self) -> None:
        stream = InMemoryEventStream(history_size=2)
        await stream.publish("event.one")
        await stream.publish("event.two")
        await stream.publish("event.three")

        recent = await stream.recent(limit=10)
        self.assertEqual([item.topic for item in recent], ["event.two", "event.three"])
        await stream.close()


if __name__ == "__main__":
    unittest.main()
