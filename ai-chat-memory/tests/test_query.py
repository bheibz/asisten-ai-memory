import pytest
from app.core.query_classifier import QueryClassifier


@pytest.fixture
def clf():
    return QueryClassifier()


@pytest.mark.asyncio
async def test_simple_greeting(clf):
    q = await clf.classify("halo")
    assert q.complexity == "simple"
    assert q.category == "casual"
    assert q.needs_search == False
    assert q.needs_time == False
    assert q.needs_memory == False
    assert q.needs_tools == False


@pytest.mark.asyncio
async def test_complex_coding(clf):
    q = await clf.classify("buatkan aplikasi web dengan python flask")
    assert q.complexity == "complex"
    assert q.category == "coding"
    assert q.needs_search == False


@pytest.mark.asyncio
async def test_factual_hijri(clf):
    q = await clf.classify("tanggal hijriyah sekarang berapa")
    assert q.needs_search == True


@pytest.mark.asyncio
async def test_factual_siapa(clf):
    q = await clf.classify("siapa presiden indonesia sekarang")
    assert q.needs_search == True
    assert q.complexity != "simple"


@pytest.mark.asyncio
async def test_search_explicit(clf):
    q = await clf.classify("cari berita AI terbaru")
    assert q.needs_tools == True
    assert q.needs_search == True


@pytest.mark.asyncio
async def test_cek_internet(clf):
    q = await clf.classify("cek di internet")
    assert q.needs_tools == True
    assert q.needs_search == True


@pytest.mark.asyncio
async def test_memory_trigger(clf):
    q = await clf.classify("ingat bahwa aku suka kopi")
    assert q.needs_memory == True


@pytest.mark.asyncio
async def test_time_query(clf):
    q = await clf.classify("jam berapa sekarang")
    assert q.needs_time == True


@pytest.mark.asyncio
async def test_hijri_query(clf):
    q = await clf.classify("tanggal islam sekarang")
    assert q.complexity in ("moderate",)


@pytest.mark.asyncio
async def test_english_greeting(clf):
    q = await clf.classify("hello")
    assert q.complexity == "simple"
    assert q.needs_search == False


@pytest.mark.asyncio
async def test_writing_category(clf):
    q = await clf.classify("tulis cerita pendek")
    assert q.category == "writing"


@pytest.mark.asyncio
async def test_research_category(clf):
    q = await clf.classify("cari informasi tentang AI")
    assert q.category == "research"


@pytest.mark.asyncio
async def test_factual_berapa(clf):
    q = await clf.classify("berapa jumlah penduduk indonesia")
    assert q.needs_search == True


@pytest.mark.asyncio
async def test_factual_sejarah(clf):
    q = await clf.classify("sejarah kemerdekaan indonesia")
    assert q.needs_search == True
