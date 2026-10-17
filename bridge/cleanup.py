"""Conservative handling of explicit spoken corrections before cloud cleanup.

Only typed times, dates and quantities are resolved locally. Ambiguous references,
quoted examples and hypothetical corrections stay literal. The cloud still does
punctuation, filler removal and sentence organization; no extra model is used.
"""
from collections import Counter
import re

DIGITS = r'[0-9零〇一二两三四五六七八九十百千万]{1,16}(?:\.[0-9]{1,6})?'
VALUE = rf'(?:{DIGITS}年{DIGITS}月{DIGITS}(?:日|号)|{DIGITS}月{DIGITS}(?:日|号)|星期[一二三四五六日天]|周[一二三四五六日天]|{DIGITS}\s*(?:万元|千元|小时|分钟|公斤|千克|毫升|公里|点(?:半)?|时|月|日|号|天|个|件|箱|人|份|场|次|台|套|瓶|本|张|名|年|岁|元|万|吨|米|克|升|%|％))'
FIND_VALUE = re.compile(VALUE)
QUOTED = re.compile(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"|‘[^’]*’|`[^`]*`')
HYPOTHETICAL = re.compile(r'如果|假如|假设|例如|比如|示例|原话|有人说|他说|她说|\b(?:if|suppose|example|quote)\b|he said|she said', re.I)
INLINE = re.compile(rf'(?P<old>{VALUE})(?P<tail>开会|提交|交付|截止|完成|送达)?[，,、\s—-]*(?:哦不|噢不|啊不|说错了|不对)[，,、\s—-]*(?P<new>{VALUE})')
DELAYED = re.compile(rf'(?:[，,。；;\s]*(?:哦对了|噢对了|对了)[，,\s]*)?'
    rf'(?:刚才|前面|之前)(?:说的|提到的|讲的)?[，,\s]*(?P<old>{VALUE})'
    rf'[，,\s]*(?:不对|说错了|错了)[，,\s]*(?:应该是|应为|改成|改为|更正为)[，,\s]*'
    rf'(?P<new>{VALUE})[。；;，,\s]*')


def _number(value):
    value = value.replace('两','二').replace('〇','零')
    if value.isascii() and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
        return value.lstrip('0') or '0'
    digits = dict(zip('零一二三四五六七八九',range(10)))
    if not any(c in value for c in '十百千万'):
        if all(c in digits for c in value):return ''.join(str(digits[c]) for c in value)
        return value
    total = section = digit = 0
    for c in value:
        if c in digits:digit=digits[c]
        elif c in '十百千':section+=(digit or 1)*{'十':10,'百':100,'千':1000}[c];digit=0
        elif c=='万':total+=(section+digit or 1)*10000;section=digit=0
        else:return value
    return str(total+section+digit)


def canonical(value):
    value = re.sub(r'\s+','',value)
    if value.startswith(('星期','周')):
        return 'weekday:'+value.removeprefix('星期').removeprefix('周').replace('天','日')
    return re.sub(DIGITS,lambda m:_number(m[0]),value).replace('％','%').casefold()


def _kind(value):
    value = re.sub(r'\s+','',value)
    if value.startswith(('星期','周')):return 'weekday'
    if re.search(r'(?:点半|点|时)$',value):return 'time'
    if re.search(r'(?:月|日|号|天)$',value):return 'date:'+re.sub(DIGITS,'',value)
    return 'quantity:'+re.sub(DIGITS,'',value)


def _protected(text,start,end):
    if any(m.start()<end and m.end()>start for m in QUOTED.finditer(text)):return True
    sentence_start=max(text.rfind(c,0,start) for c in '。！？\n')+1
    return bool(HYPOTHETICAL.search(text[sentence_start:start]))


def resolve_corrections(text):
    # Limit work and prefer preserving a doubtful utterance to guessing its target.
    for _ in range(32):
        changed=False
        for m in DELAYED.finditer(text):
            if _protected(text,m.start(),m.end()) or _kind(m['old'])!=_kind(m['new']):continue
            candidates=[v for v in FIND_VALUE.finditer(text[:m.start()])
                        if canonical(v[0])==canonical(m['old']) and not _protected(text,v.start(),v.end())]
            if len(candidates)!=1:continue
            target=candidates[0]
            left=text[:target.start()]+m['new']+text[target.end():m.start()]
            right=text[m.end():]
            separator='。' if left and left[-1] not in '。！？；;\n' else ''
            text=left+separator+right
            changed=True;break
        if not changed:break
    for _ in range(32):
        changed=False
        for m in INLINE.finditer(text):
            if _protected(text,m.start(),m.end()) or _kind(m['old'])!=_kind(m['new']):continue
            tail=m['tail'] or ''
            # Keep an abandoned predicate if it is not repeated with the correction.
            if tail and text[m.end():].startswith(tail):tail=''
            text=text[:m.start()]+m['new']+tail+text[m.end():]
            changed=True;break
        if not changed:break
    english=re.compile(r"\bat\s+(?P<old>\d+(?::\d+)?)(?P<tail>\s+(?:this\s+)?(?:morning|afternoon|evening|tonight))?[—,;\s-]+(?:no|sorry|actually|I mean)[,\s]+(?:at\s+)?(?P<new>\d+(?::\d+)?)\b",re.I)
    for m in list(english.finditer(text))[::-1]:
        if not _protected(text,m.start(),m.end()):
            text=text[:m.start()]+'at '+m['new']+(m['tail'] or '')+text[m.end():]
    return text


def _compact(text):
    return re.sub(r'[\s，,。.!！?？；;：:、—-]+','',text).casefold()


def preservation_error(source,result):
    """Reject observable losses of protected content, rather than repairing a guess."""
    compact=_compact(result)
    for quote in QUOTED.finditer(source):
        if _compact(quote[0]) not in compact:return 'quoted-content'
    # Comma-separated repeated phrases express emphasis, unlike a partial stutter.
    for repeat in re.finditer(r'([\u4e00-\u9fff]{2,16})[，,]\s*\1',source):
        phrase=_compact(repeat[1])
        if compact.count(phrase)<_compact(source).count(phrase):return 'intentional-repetition'
    for repeat in re.finditer(r'\b(very|really|never)\s+\1\b',source,re.I):
        if not re.search(r'\b'+re.escape(repeat[1])+r'\s+'+re.escape(repeat[1])+r'\b',result,re.I):
            return 'intentional-repetition'
    # Compare typed values after explicit corrections have been resolved. Model
    # numbering/layout may add values, but existing alternatives must remain.
    def inventory(text):
        structured=[m for m in FIND_VALUE.finditer(text) if not (m.start() and text[m.start()-1]=='第')]
        result=Counter(canonical(m[0]) for m in structured)
        for number in re.finditer(r'(?<![a-zA-Z0-9])\d+(?::\d+)?(?:\.\d+)?(?![0-9])',text):
            if not any(v.start()<number.end() and v.end()>number.start() for v in structured):
                result['number:'+number[0]]+=1
        return result
    values,remaining=inventory(source),inventory(result)
    if values-remaining:return 'numbers-or-dates'
    for name in re.finditer(r'(?:发给|交给|通知|联系|抄送)([\u4e00-\u9fff]{2,4})(?=[，。；、\s]|$)',source):
        if name[1] not in result:return 'recipient-name'
    for name in re.finditer(r'(?:send to|notify|contact|copy to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',source):
        if _compact(name[1]) not in compact:return 'recipient-name'
    for negation in ('不要','不能','不得','没有','不是','不再','不会','不应','没','未'):
        if source.count(negation)>result.count(negation):return 'negation'
    for negation in re.findall(r"\b(?:not|never|no|cannot|don't|doesn't|isn't|won't)\b",source,re.I):
        if len(re.findall(r'\b'+re.escape(negation)+r'\b',result,re.I))<len(re.findall(r'\b'+re.escape(negation)+r'\b',source,re.I)):
            return 'negation'
    return None
