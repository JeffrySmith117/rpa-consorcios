"""Teste rápido da integração com WhatsApp, fora da interface.

Uso (dentro de backend/, com o .env configurado):

    python -m app.whatsapp.testar 11999998888
    python -m app.whatsapp.testar 11999998888 --template   # só Meta: envia o template hello_world

Fluxo recomendado com a Meta antes da demonstração:
  1. --template  → confirma token, Phone Number ID e número autorizado
  2. responda qualquer coisa no WhatsApp (abre a janela de 24h)
  3. sem --template → confirma que texto livre (o que o sistema envia) chega
"""
import argparse
import sys

from app.config import get_settings
from app.exceptions import AppError
from app.services.envios import normalizar_numero
from app.whatsapp.providers import MetaCloudAPI, criar_provedor


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa o envio de WhatsApp com as credenciais do .env")
    parser.add_argument("numero", help="Número de destino, ex.: 11999998888")
    parser.add_argument("--template", action="store_true", help="(Meta) envia o template hello_world")
    args = parser.parse_args()

    s = get_settings()
    print(f"Provedor configurado: {s.whatsapp_provider}")
    try:
        numero = normalizar_numero(args.numero)
        provedor = criar_provedor(s)
        if args.template:
            if not isinstance(provedor, MetaCloudAPI):
                print("--template só se aplica ao provedor 'meta'.")
                return 2
            resultado = provedor.enviar_template(numero)
        else:
            resultado = provedor.enviar(numero, "✅ Teste do RPA Consórcios BCB: integração com WhatsApp funcionando.")
    except AppError as e:
        print(f"❌ Falhou: {e.mensagem}")
        return 1
    print(f"✅ Enviado para {numero} via {resultado.provedor} (id: {resultado.message_id})")
    if s.whatsapp_provider == "mock":
        print("   (mock: nada foi enviado de verdade — configure WHATSAPP_PROVIDER=meta ou twilio no .env)")
    return 0


if __name__ == "__main__":
    sys.exit(main())