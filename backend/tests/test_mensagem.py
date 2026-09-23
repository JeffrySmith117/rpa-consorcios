from app.services.mensagem import formatar_valor, formatar_variacao, gerar_mensagem
from app.services.tratamento import estruturar


def test_formatacao_pt_br():
    assert formatar_valor(3_202_550, "un") == "3,2 milhões"
    assert formatar_valor(1_700_000, "un") == "1,7 milhão"
    assert formatar_valor(169_540, "un") == "169,5 mil"
    assert formatar_valor(70.39e9, "R$") == "R$ 70,4 bi"
    assert formatar_valor(21.19, "%") == "21,19%"
    assert formatar_valor(217, "meses") == "217 meses"


def test_formatacao_variacao():
    assert formatar_variacao({"tipo": "pct", "valor": 7.62}) == " (▲ +7,6%)"
    assert formatar_variacao({"tipo": "pp", "valor": -0.12}) == " (▼ -0,12 p.p.)"
    assert formatar_variacao({"tipo": "pct", "valor": 0.01}) == " (estável)"
    assert formatar_variacao(None) == ""


def test_mensagem_usa_dados_da_consulta(registros):
    dados, _ = estruturar("202606", "IMOVEIS", "SP", registros["202606"], registros["202603"])
    texto = gerar_mensagem("  maria  de souza ", dados)

    assert texto.startswith("Olá, Maria!")
    assert "jun/2026" in texto and "Imóveis" in texto
    assert "Cotas ativas: *3,2 milhões*" in texto
    assert "📍 *SP*" in texto and "1º lugar" in texto
    assert "Variações em relação a mar/2026" in texto


def test_mensagem_sem_trimestre_anterior_nao_cita_variacao(registros):
    dados, _ = estruturar("202606", "TOTAL", None, registros["202606"], None)
    texto = gerar_mensagem("Ana", dados)
    assert "▲" not in texto and "Variações" not in texto
    assert "📍" not in texto
