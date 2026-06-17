import time
import httpx


def executar_com_retry(func, tentativas: int = 3, espera: float = 0.5):
    """
    Executa func() com retry em falhas de transporte httpx.
    Levanta RuntimeError com mensagem amigável após esgotar tentativas.
    """
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            return func()
        except (
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.TimeoutException,
            httpx.TransportError,
        ) as exc:
            ultimo_erro = exc
            time.sleep(espera * tentativa)
    raise RuntimeError(
        "Falha temporária de comunicação com o Supabase. Tente novamente em instantes."
    ) from ultimo_erro
