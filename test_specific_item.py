from services.steam_market import get_item_price_via_csgostash

def test_specific_item():
    """Testa a obtenção de preço para itens específicos com diferentes condições."""
    test_items = [
        # Itens normais em diferentes condições
        "AK-47 | Asiimov (Factory New)",
        "AK-47 | Asiimov (Minimal Wear)",
        "AK-47 | Asiimov (Field-Tested)",
        "AK-47 | Asiimov (Well-Worn)",
        "AK-47 | Asiimov (Battle-Scarred)",
        
        # StatTrak item
        "StatTrak™ AK-47 | Redline (Field-Tested)",
        
        # Item popular
        "AWP | Dragon Lore (Field-Tested)",
        
        # Item comum
        "Glock-18 | Water Elemental (Minimal Wear)"
    ]
    
    print("=== TESTE DE PREÇOS VIA CSGOSkins.gg ===\n")
    
    for item in test_items:
        print(f"\nTestando item: {item}")
        try:
            price_data = get_item_price_via_csgostash(item)
            if price_data:
                print(f"RESULTADO: {price_data['price']} {price_data['currency']}")
                if price_data.get('estimated'):
                    print("Aviso: Preço estimado (não encontrado diretamente)")
            else:
                print("RESULTADO: Não foi possível obter o preço.")
        except Exception as e:
            print(f"ERRO: {e}")
        
        # Separador
        print("-" * 40)
    
    print("\nTestes finalizados!")

if __name__ == "__main__":
    test_specific_item() 