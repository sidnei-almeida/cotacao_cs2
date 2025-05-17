import requests
import re
from selectolax.parser import HTMLParser

def test_csgoskins(item_name="AK-47 | Asiimov (Field-Tested)"):
    """
    Testa a obtenção de preços via CSGOSkins.gg usando o User-Agent de iPhone que funcionou nos testes.
    """
    # Formatar o nome do item
    cleaned_name = item_name.replace("StatTrak™ ", "")
    base_parts = cleaned_name.split(" (")
    base_name = base_parts[0].strip()
    formatted_name = base_name.lower().replace(" | ", "-").replace(" ", "-")
    formatted_name = re.sub(r'[^\w\-]', '', formatted_name)
    
    # URL para o item
    url = f"https://csgoskins.gg/items/{formatted_name}"
    print(f"URL: {url}")
    
    # Headers com User-Agent de iPhone que funcionou nos testes anteriores
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # Fazer a requisição
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Tamanho da resposta: {len(response.text)} bytes")
        
        if response.status_code == 200:
            # Parser HTML
            parser = HTMLParser(response.text)
            title = parser.css_first('title')
            if title:
                print(f"Título da página: {title.text()}")
            
            # Extrair todos os preços do HTML
            all_text = parser.body.text() if parser.body else ""
            price_matches = re.findall(r'(Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)(?:.*?)(\$|R\$|€|£|¥)\s*([0-9.,]+)', all_text)
            
            if price_matches:
                print(f"Encontradas {len(price_matches)} correspondências de preços:")
                for found_condition, symbol, price_text in price_matches:
                    print(f"  - {found_condition}: {symbol}{price_text}")
                    
                # Verificar se há preços para a condição específica do item
                if len(base_parts) > 1:
                    condition = base_parts[1].replace(")", "").strip()
                    matching_prices = [match for match in price_matches if match[0].lower() == condition.lower()]
                    if matching_prices:
                        print(f"\nPreços para condição específica ({condition}):")
                        for found_condition, symbol, price_text in matching_prices:
                            print(f"  - {symbol}{price_text}")
            else:
                print("Nenhum padrão de preço encontrado com o formato específico.")
                
                # Tentar um regex mais simples para qualquer padrão de preço
                general_prices = re.findall(r'(\$|R\$|€|£|¥)\s*([0-9.,]+)', all_text)
                if general_prices:
                    print(f"Encontrados {len(general_prices)} preços genéricos:")
                    for symbol, price_text in general_prices[:10]:  # Mostrar até 10
                        print(f"  - {symbol}{price_text}")
                else:
                    print("Nenhum preço encontrado no texto.")
                    
            # Salvar resposta para análise posterior
            with open('csgoskins_response.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("Resposta salva em 'csgoskins_response.html'")
            
        else:
            print(f"Erro: Código de status {response.status_code}")
            
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("==== Testando CSGOSkins.gg para AK-47 Asiimov ====")
    test_csgoskins("AK-47 | Asiimov (Field-Tested)")
    
    print("\n==== Testando CSGOSkins.gg para AWP Asiimov ====")
    test_csgoskins("AWP | Asiimov (Field-Tested)")
    
    print("\n==== Testando CSGOSkins.gg para item StatTrak ====")
    test_csgoskins("StatTrak™ AK-47 | Redline (Field-Tested)") 