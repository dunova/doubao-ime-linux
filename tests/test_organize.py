import asyncio
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from organize import parse_sse, OrganizeError, safe_text
from audio import Session
from settings import merge_supported_settings


def stream(events):
    return ''.join('event:'+kind+'\ndata:'+(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False))+'\n\n'
                   for kind,value in events).encode()


class Protocol(unittest.TestCase):
    def test_completed_revises_streamed_layout(self):
        raw=stream([('scene.delta',{'content':'1.事项\n\n','no_rewrite':False}),
            ('scene.completed',{'content':'1.事项\n2.讨论'}),('done','[DONE]')])
        self.assertEqual(parse_sse(raw,'原文',200),'1.事项\n2.讨论')

    def test_no_rewrite_retains_original(self):
        raw=stream([('scene.delta',{'content':'','no_rewrite':True}),
            ('scene.completed',{'content':''}),('done','[DONE]')])
        self.assertEqual(parse_sse(raw,'原文',200),'原文')

    def test_truncation_errors_and_control_characters_never_commit(self):
        cases=[[], [('scene.delta',{'content':'未完成'})],
            [('done','[DONE]')], [('scene.error',{'code':500})],
            [('scene.completed',{'content':'错误\x1b[31m'}),('done','[DONE]')],
            [('scene.completed',{'content':'好'}),('done','[DONE]'),('scene.delta',{'content':'坏'})],
            [('scene.delta',{'content':'冲突','no_rewrite':True}),('scene.completed',{'content':''}),('done','[DONE]')]]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(OrganizeError):parse_sse(stream(case),'原文',200)
        with self.assertRaises(OrganizeError):parse_sse(b'\xff','原文',200)
        with self.assertRaises(OrganizeError):parse_sse(b'','原文',403)
        self.assertFalse(safe_text('x\ty'));self.assertTrue(safe_text('x\ny'))

    def test_only_smart_text_voice_option_is_merged(self):
        before={'keyboard':{},'voice':{'smartTextEnabled':False,'selectedMicrophoneId':'old'}}
        after={'keyboard':{},'voice':{'smartTextEnabled':True,'selectedMicrophoneId':'new'}}
        merged,changes=merge_supported_settings(before,after,before)
        self.assertEqual(merged['voice'],{'smartTextEnabled':True,'selectedMicrophoneId':'old'})
        self.assertEqual(changes,{'voice.smartTextEnabled':True})


class FakeOrganizer:
    error=None
    cancel_on_finish=False
    instances=[]
    def __init__(self,cancel):self.cancel=cancel;self.closed=False;self.instances.append(self)
    async def start(self):pass
    async def finish(self,text):
        if self.cancel_on_finish:self.cancel.set();raise OrganizeError('cancelled')
        if self.error:raise OrganizeError(self.error)
        return '整理后\n第二段'
    async def close(self):self.closed=True


class Sessions(unittest.IsolatedAsyncioTestCase):
    async def exercise(self,error=None,cancel=False):
        FakeOrganizer.error=error;FakeOrganizer.cancel_on_finish=cancel
        events=[];s=Session(lambda *event:events.append(event),organize=True)
        async def speech():return {'text':'原始转写'}
        with patch('audio.Organizer',FakeOrganizer),patch.object(s,'run',speech):
            result=await s.run_with_organizer()
        self.assertTrue(FakeOrganizer.instances[-1].closed)
        return result

    async def test_official_result_replaces_only_completed_transcription(self):
        result=await self.exercise();self.assertEqual(result['text'],'整理后\n第二段');self.assertTrue(result['organized'])

    async def test_timeout_falls_back_to_transcript(self):
        result=await self.exercise(error='timeout');self.assertEqual(result['text'],'原始转写');self.assertEqual(result['organize_status'],'fallback')

    async def test_cancel_during_organization_never_falls_back_into_application(self):
        result=await self.exercise(cancel=True);self.assertIsNone(result['text']);self.assertEqual(result['organize_status'],'cancelled')

if __name__=='__main__':unittest.main()
