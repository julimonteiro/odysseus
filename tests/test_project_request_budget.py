import pytest
from src.project_request_budget import fit_local_request

class Response:
    def __init__(self,data):self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data
class Client:
    def __init__(self):self.counts=[]
    async def post(self,url,*,json,**kwargs):
        if url.endswith('apply-template'):
            # The server's tokenizer charges schemas AND template overhead.
            return Response({'prompt':'x'*(sum(len(str(m.get('content',''))) for m in json['messages'])+3000)})
        n=len(json['content']);self.counts.append(n);return Response({'tokens':[0]*n})

@pytest.mark.asyncio
async def test_exact_rendered_count_includes_schemas_and_keeps_user():
    client=Client();messages=[{'role':'user','content':'Implement filetree.'},{'role':'assistant','content':'code '*3000}]
    fitted,cap=await fit_local_request(client,'http://127.0.0.1:8081/v1','model',messages,[{'name':'read_file'}],8192)
    assert client.counts[0]>8192 and client.counts[-1]+cap+128<=8192
    assert any(m['role']=='user' for m in fitted)
    assert len(messages[-1]['content'])==15000

@pytest.mark.asyncio
async def test_remote_requests_are_unchanged():
    messages=[{'role':'user','content':'hi'}]
    fitted,cap=await fit_local_request(None,'https://example.com/v1','model',messages,[],8192)
    assert fitted is messages and cap==0

@pytest.mark.asyncio
async def test_unsupported_tokenizer_falls_back_with_schema_allowance():
    class Unsupported:
        async def post(self,*args,**kwargs):raise RuntimeError('unsupported')
    from src.model_context import estimate_tokens
    messages=[{'role':'user','content':'keep this request'},{'role':'assistant','content':'x'*40000}]
    fitted,cap=await fit_local_request(Unsupported(),'http://localhost:8081/v1','model',messages,[{'description':'schema'*500}],8192)
    assert estimate_tokens(fitted)<5000 and cap==1024
    assert fitted[0]['role']=='user'

@pytest.mark.asyncio
async def test_fallback_rejects_irreducible_protected_context():
    class Unsupported:
        async def post(self,*args,**kwargs):raise RuntimeError('unsupported')
    messages=[{'role':'system','content':'Protected text '*10000,'_protected':True},{'role':'user','content':'Continue'}]
    with pytest.raises(ValueError,match='Protected context'):
        await fit_local_request(Unsupported(),'http://localhost:8081/v1','model',messages,[],8192)
