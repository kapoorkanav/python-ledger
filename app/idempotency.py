DEPOSIT="deposit"
WITHDRAW="withdraw"
TRANSFER="transfer"

def entry_key(operation:str, client_key: str, leg: str)->str:
    return f"{operation}:{client_key}-{leg}"