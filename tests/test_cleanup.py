"""Issue #2: preserve intent while removing explicit spoken self-corrections."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from cleanup import resolve_corrections, preservation_error

class Corrections(unittest.TestCase):
    def test_times_dates_and_quantities(self):
        examples={
            '今天下午2点，哦不，3点开会。':'今天下午3点开会。',
            '周三提交，哦不，周四提交。':'周四提交。',
            '采购20个，哦不，30个零件。':'采购30个零件。',
            '10月12日，不对，10月13日交付。':'10月13日交付。',
            "Let's meet at 2 this afternoon—no, at 3.":"Let's meet at 3 this afternoon.",
        }
        for source,expected in examples.items():
            with self.subTest(source=source):self.assertEqual(resolve_corrections(source),expected)

    def test_delayed_revision_uses_unique_reference_in_full_passage(self):
        source=('帮我记一下明天的安排。第一件事是下午3点开会，先讨论预算，再看人员安排。'
            '第二件事是会后把会议纪要发给王小明，预算20万元，保留两场会议作比较。'
            '哦对了，刚才说的三点不对，改成4点。不要取消任何一场会议，也不要修改预算。')
        result=resolve_corrections(source)
        self.assertIn('下午4点开会',result)
        self.assertNotIn('不对',result);self.assertNotIn('3点',result)
        for important in ['王小明','20万元','保留两场会议作比较','不要取消任何一场会议','不要修改预算']:
            self.assertIn(important,result)
        self.assertIn('。不要取消',result)

    def test_meaningful_alternatives_negation_and_repetition_stay_literal(self):
        for source in ['请比较下午2点和3点的两场会议。','我们不是要取消会议，也不是要减少人数。',
                       '这个问题很重要，很重要，请一定记住。','请再说一遍，不要取消，不要取消。',
                       '请采购2箱，而不是3箱。','三点不是四点，二者不可混淆。']:
            with self.subTest(source=source):self.assertEqual(resolve_corrections(source),source)

    def test_quoted_hypothetical_or_ambiguous_corrections_are_not_guessed(self):
        for source in ['他说“2点，哦不，3点开会”。','例如2点，哦不，3点开会，这句话需要保留。',
                       '如果刚才3点不对，改成4点会怎样？','2点开会，2点还有电话。刚才说的2点不对，改成3点。',
                       'If I say at 2, no, at 3, retain that quote.']:
            with self.subTest(source=source):self.assertEqual(resolve_corrections(source),source)

class PreserveIntent(unittest.TestCase):
    def test_suppressed_alternative_or_quantity_is_rejected(self):
        self.assertEqual(preservation_error('比较2点和3点的会议。','比较3点的会议。'),'numbers-or-dates')
        self.assertEqual(preservation_error('预算20万元。','预算30万元。'),'numbers-or-dates')
        self.assertEqual(preservation_error('Compare the 2 pm and 3 pm meetings.','Compare the 3 pm meeting.'),'numbers-or-dates')
        self.assertIsNone(preservation_error('下午三点开会。','下午 3 点开会。'))

    def test_deliberate_emphasis_negation_and_recipient_cannot_disappear(self):
        for source,result,reason in [
            ('这个问题很重要，很重要，请记住。','这个问题很重要，请记住。','intentional-repetition'),
            ('This is very very important.','This is very important.','intentional-repetition'),
            ('不要取消会议。','取消会议。','negation'),
            ("Don't cancel the meeting.",'Cancel the meeting.','negation'),
            ('把纪要发给王小明。','把纪要发给大家。','recipient-name'),
            ('保留原话“2点，哦不，3点”。','保留原话“3点”。','quoted-content')]:
            with self.subTest(source=source):self.assertEqual(preservation_error(source,result),reason)

    def test_filler_and_abandoned_repetitions_can_be_cleaned_without_losing_facts(self):
        self.assertIsNone(preservation_error('嗯那个我我想说，明天下午3点开会，预算20万元。',
                                            '明天下午3点开会，预算20万元。'))
        self.assertIsNone(preservation_error('明天下午3点开会，预算20万元。',
                                            '1. 明天下午3点开会。\n2. 预算20万元。'))


class Pipeline(unittest.IsolatedAsyncioTestCase):
    async def test_official_request_contains_full_corrected_passage(self):
        import asyncio,json,threading
        from types import SimpleNamespace
        from organize import Organizer
        class Input:
            def write(self,data):self.data=data
            async def drain(self):pass
        o=Organizer(threading.Event());sink=Input();o.process=SimpleNamespace(stdin=sink)
        o.reader=asyncio.create_task(asyncio.sleep(0));await o.reader
        o.status=200;o.ready=True
        o.raw.extend(b'event:scene.delta\ndata:{"content":"","no_rewrite":true}\n\nevent:scene.completed\ndata:{"content":""}\n\nevent:done\ndata:[DONE]\n\n')
        source='下午2点开会。预算20万元。刚才说的2点不对，改成3点。不要取消会议。'
        result=await o.finish(source)
        self.assertEqual(result,'下午3点开会。预算20万元。不要取消会议。')
        self.assertEqual(json.loads(sink.data)['query'],result)

    async def test_model_loss_is_visible_and_falls_back_to_accepted_transcript(self):
        import asyncio,json,threading
        from types import SimpleNamespace
        from unittest.mock import patch
        from audio import Session
        from organize import Organizer
        class Input:
            def write(self,data):pass
            async def drain(self):pass
        class UnsafeModel(Organizer):
            async def start(self):
                self.process=SimpleNamespace(stdin=Input());self.reader=asyncio.create_task(asyncio.sleep(0))
                await self.reader;self.status=200;self.ready=True
                payload=json.dumps({'content':'取消会议。'},ensure_ascii=False)
                self.raw.extend(('event:scene.completed\ndata:'+payload+'\n\nevent:done\ndata:[DONE]\n\n').encode())
            async def close(self):pass
        s=Session(lambda *args:None,organize=True)
        async def speech():return {'text':'不要取消会议。'}
        with patch('audio.Organizer',UnsafeModel),patch.object(s,'run',speech):result=await s.run_with_organizer()
        self.assertEqual(result['text'],'不要取消会议。')
        self.assertEqual(result['organize_error'],'meaning-check')
        self.assertEqual(result['organize_status'],'fallback')

    async def test_literal_mode_never_runs_cleanup_or_cloud(self):
        from unittest.mock import patch
        from audio import Session
        source='今天下午2点，哦不，3点开会。'
        s=Session(lambda *args:None,organize=False)
        async def speech():return {'text':source}
        with patch('audio.Organizer') as factory,patch.object(s,'run',speech):result=await s.run_with_organizer()
        factory.assert_not_called();self.assertEqual(result['text'],source)


if __name__=='__main__':unittest.main()
