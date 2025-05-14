import re
from urllib.parse import urlencode
import requests
import jwt
from datetime import datetime, timedelta
import os

# Configurações para JWT
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "sua_chave_secreta_muito_longa_e_segura")  # Usar variável de ambiente
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# URL para o OpenID da Steam
STEAM_OPENID_URL = 'https://steamcommunity.com/openid/login'

def steam_login_url(redirect_url):
    """
    Gera URL para login via Steam OpenID
    
    Args:
        redirect_url: URL para redirecionamento após o login
        
    Returns:
        URL completa para o login
    """
    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.mode': 'checkid_setup',
        'openid.return_to': redirect_url,
        'openid.realm': redirect_url.rsplit('/', 1)[0] + '/',
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"

def validate_steam_login(params):
    """
    Valida resposta do Steam OpenID e retorna SteamID64
    
    Args:
        params: Parâmetros recebidos do redirecionamento
        
    Returns:
        SteamID64 do usuário se autenticação válida, None caso contrário
    """
    # Criar uma cópia dos parâmetros para não modificar o original
    validation_params = params.copy()
    validation_params['openid.mode'] = 'check_authentication'
    
    response = requests.post(STEAM_OPENID_URL, data=validation_params)
    
    if 'is_valid:true' in response.text:
        # Extrair o SteamID64 da resposta
        steam_id_match = re.search(r'openid.claimed_id.*?(\d+)', str(params))
        if steam_id_match:
            return steam_id_match.group(1)
    return None

def create_jwt_token(data: dict, expires_delta: timedelta = None):
    """
    Cria um token JWT para autenticação
    
    Args:
        data: Dados a serem incluídos no token
        expires_delta: Tempo de expiração opcional
        
    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    
    # Definir expiração
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    
    # Criar o token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_jwt_token(token: str):
    """
    Verifica e decodifica um token JWT
    
    Args:
        token: Token JWT a ser verificado
        
    Returns:
        Dados decodificados do token ou None se inválido
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None 