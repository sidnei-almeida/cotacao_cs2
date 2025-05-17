"""
Utilitário para atualização semanal dos preços das skins no banco de dados.
"""
import time
import schedule
import threading
import logging
from datetime import datetime
from typing import List, Dict

from utils.database import get_outdated_skins, set_metadata, get_metadata, get_stats
from utils.database import get_outdated_cases
from services.steam_market import get_item_price_via_csgostash, process_scraped_price
from utils.database import save_skin_price
from utils.case_scraper import update_cases_database

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações
UPDATE_BATCH_SIZE = 100  # Número de skins a atualizar por execução
UPDATE_DELAY_SECONDS = 5  # Tempo de espera entre cada skin (para evitar bloqueios)
CASE_UPDATE_INTERVAL_HOURS = 24  # Intervalo em horas para atualização das caixas


def update_skin_prices(max_items: int = UPDATE_BATCH_SIZE, days_old: int = 7) -> Dict:
    """
    Atualiza os preços das skins mais antigas no banco de dados.
    
    Args:
        max_items: Número máximo de itens a atualizar por vez
        days_old: Dias para considerar um preço como desatualizado
        
    Returns:
        Dicionário com estatísticas da atualização
    """
    logger.info(f"Iniciando atualização de preços de skins desatualizadas...")
    
    # Obter skins desatualizadas
    outdated_skins = get_outdated_skins(days=days_old, limit=max_items)
    total_items = len(outdated_skins)
    
    logger.info(f"Encontradas {total_items} skins desatualizadas para atualizar")
    
    # Estatísticas da atualização
    stats = {
        'total_skins': total_items,
        'updated_skins': 0,
        'failed_skins': 0,
        'total_value_before': 0,
        'total_value_after': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None
    }
    
    # Atualizar preços
    for i, skin in enumerate(outdated_skins):
        try:
            market_hash_name = skin['market_hash_name']
            currency = skin['currency']
            app_id = skin['app_id']
            old_price = skin['price']
            
            logger.info(f"[{i+1}/{total_items}] Atualizando {market_hash_name}...")
            
            # Obter novo preço via CSGOStash em vez de Steam
            new_price_raw = get_item_price_via_csgostash(market_hash_name, currency)
            if new_price_raw:
                new_price = process_scraped_price(market_hash_name, new_price_raw.get("price", 0))
                
                # Acumular valores para estatísticas
                stats['total_value_before'] += old_price
                stats['total_value_after'] += new_price
                
                # Salvar novo preço no banco
                save_skin_price(market_hash_name, new_price, currency, app_id)
                
                logger.info(f"  ✓ Atualizado: {market_hash_name} - Preço anterior: {old_price}, Novo preço: {new_price}")
                stats['updated_skins'] += 1
            else:
                logger.warning(f"  ✗ Falha: Não foi possível obter preço para {market_hash_name}")
                stats['failed_skins'] += 1
                
            # Aguardar para evitar bloqueios
            time.sleep(UPDATE_DELAY_SECONDS)
            
        except Exception as e:
            logger.error(f"  ✗ Erro ao atualizar {skin['market_hash_name']}: {e}")
            stats['failed_skins'] += 1
    
    # Registrar a última atualização
    stats['end_time'] = datetime.now().isoformat()
    set_metadata('last_weekly_update', datetime.now().isoformat())
    
    # Calcular diferença média
    if stats['updated_skins'] > 0:
        avg_diff = (stats['total_value_after'] - stats['total_value_before']) / stats['updated_skins']
        stats['average_price_change'] = round(avg_diff, 2)
    else:
        stats['average_price_change'] = 0
    
    logger.info(f"Atualização concluída: {stats['updated_skins']} skins atualizadas, "
          f"{stats['failed_skins']} falhas")
    
    return stats


def update_case_prices() -> Dict:
    """
    Atualiza os preços e conteúdos das caixas no banco de dados.
    Esta função é o ponto de entrada principal para atualização de caixas.
    
    Returns:
        Dicionário com estatísticas da atualização
    """
    logger.info("Iniciando atualização de preços e conteúdos das caixas...")
    
    try:
        # A função update_cases_database do módulo case_scraper faz todo o trabalho
        # de buscar os dados do stash.clash.gg e salvar no banco de dados
        stats = update_cases_database()
        
        # Registrar a última atualização das caixas
        set_metadata('last_cases_update', datetime.now().isoformat())
        
        logger.info(f"Atualização de caixas concluída: {stats['updated_cases']} caixas atualizadas, "
               f"{stats['failed_cases']} falhas")
        
        return stats
    except Exception as e:
        logger.error(f"Erro durante a atualização das caixas: {e}")
        return {
            'error': str(e),
            'updated_cases': 0,
            'failed_cases': 0,
            'timestamp': datetime.now().isoformat()
        }


def schedule_weekly_update(day_of_week: int = 0, hour: int = 3, minute: int = 0):
    """
    Agenda uma atualização semanal dos preços.
    
    Args:
        day_of_week: Dia da semana (0-6, onde 0 é segunda-feira)
        hour: Hora do dia (0-23)
        minute: Minuto da hora (0-59)
    """
    days = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    day_name = days[day_of_week]
    
    logger.info(f"Agendando atualização semanal para {day_name} às {hour:02d}:{minute:02d}")
    
    # Definir o dia da semana para a atualização
    if day_of_week == 0:
        schedule.every().monday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    elif day_of_week == 1:
        schedule.every().tuesday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    elif day_of_week == 2:
        schedule.every().wednesday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    elif day_of_week == 3:
        schedule.every().thursday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    elif day_of_week == 4:
        schedule.every().friday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    elif day_of_week == 5:
        schedule.every().saturday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    elif day_of_week == 6:
        schedule.every().sunday.at(f"{hour:02d}:{minute:02d}").do(update_skin_prices)
    
    # Agendar atualização diária de caixas
    logger.info(f"Agendando atualização diária de caixas às 05:00")
    schedule.every().day.at("05:00").do(update_case_prices)


def run_scheduler():
    """
    Executa o agendador em uma thread separada.
    """
    logger.info("Iniciando agendador de atualização de preços...")
    
    scheduler_thread = threading.Thread(target=_scheduler_thread, daemon=True)
    scheduler_thread.start()
    
    return scheduler_thread


def _scheduler_thread():
    """
    Thread para execução do agendador.
    """
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verificar a cada minuto


def force_update_now(max_items: int = UPDATE_BATCH_SIZE):
    """
    Força uma atualização imediata das skins mais antigas.
    
    Args:
        max_items: Número máximo de itens para atualizar
        
    Returns:
        Estatísticas da atualização
    """
    logger.info("Forçando atualização imediata dos preços...")
    return update_skin_prices(max_items=max_items)


def force_update_cases_now():
    """
    Força uma atualização imediata das caixas.
    
    Returns:
        Estatísticas da atualização
    """
    logger.info("Forçando atualização imediata das caixas...")
    return update_case_prices()


def get_scheduler_status() -> Dict:
    """
    Retorna o status do agendador.
    
    Returns:
        Dicionário com informações do agendador
    """
    last_update = get_metadata('last_weekly_update', 'Nunca')
    last_cases_update = get_metadata('last_cases_update', 'Nunca')
    
    next_run = None
    next_cases_run = None
    
    for job in schedule.get_jobs():
        job_str = str(job)
        if next_run is None or job.next_run < next_run:
            next_run = job.next_run
            
        # Identificar trabalhos específicos
        if 'update_case_prices' in job_str:
            next_cases_run = job.next_run
    
    return {
        'last_update': last_update,
        'last_cases_update': last_cases_update,
        'next_update': next_run.isoformat() if next_run else 'Não agendado',
        'next_cases_update': next_cases_run.isoformat() if next_cases_run else 'Não agendado',
        'scheduled_jobs': len(schedule.get_jobs()),
        'db_stats': get_stats()
    } 