"""
Scheduler Service - Zamanlayıcı Servisi

Bu modül kassandra_openai_bot.py'den ayrıştırılmıştır.
Kaynak: kassandra_openai_bot.py satır 4342-4618

Günlük rapor, self-test, temizlik ve hatırlatma görevleri.
"""

from __future__ import annotations

import asyncio
import time as time_module
from datetime import datetime
from typing import Optional, Callable, Any


# ======================================================
# SCHEDULER JOB WRAPPERS
# ======================================================

def run_async_job(coro_func: Callable[[], Any]):
    """
    Async fonksiyonu sync scheduler'dan çalıştırmak için wrapper.
    
    Args:
        coro_func: Çalıştırılacak async fonksiyon
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro_func())
        finally:
            loop.close()
    except Exception as e:
        print(f"❌ Async job hatası: {e}")


class SchedulerService:
    """Zamanlayıcı servisi"""
    
    def __init__(
        self,
        # Servisler
        send_daily_report=None,
        send_selftest_report=None,
        cleanup_stale_flows=None,
        check_reservation_reminders=None,
        run_golden_test=None,
        # Coalescer
        coalescer=None,
        process_coalesced_message=None,
        # Ayarlar
        coalesce_window_seconds: float = 12.0,
        max_coalesce_wait_seconds: float = 25.0,
    ):
        """
        Args:
            send_daily_report: Günlük rapor gönderme fonksiyonu
            send_selftest_report: Self-test rapor gönderme fonksiyonu
            cleanup_stale_flows: Stale flow temizleme fonksiyonu
            check_reservation_reminders: Rezervasyon hatırlatma fonksiyonu
            run_golden_test: Golden test çalıştırma fonksiyonu
            coalescer: Message coalescer instance
            process_coalesced_message: Birleştirilmiş mesaj işleme fonksiyonu
            coalesce_window_seconds: Coalesce bekleme süresi
            max_coalesce_wait_seconds: Maksimum coalesce bekleme süresi
        """
        self.send_daily_report = send_daily_report
        self.send_selftest_report = send_selftest_report
        self.cleanup_stale_flows = cleanup_stale_flows
        self.check_reservation_reminders = check_reservation_reminders
        self.run_golden_test = run_golden_test
        self.coalescer = coalescer
        self.process_coalesced_message = process_coalesced_message
        self.coalesce_window_seconds = coalesce_window_seconds
        self.max_coalesce_wait_seconds = max_coalesce_wait_seconds
        
        self._scheduler = None
    
    def setup_scheduler(self, scheduler):
        """
        APScheduler'ı yapılandır.
        
        Args:
            scheduler: BackgroundScheduler instance
        """
        self._scheduler = scheduler
        
        # Coalesce job (her 2 saniyede)
        if self.coalescer:
            scheduler.add_job(
                self.check_and_flush_coalesce_buffers, 
                'interval', 
                seconds=2, 
                id='coalesce_flush_job'
            )
        
        # Günlük rapor (09:00)
        if self.send_daily_report:
            scheduler.add_job(
                self.scheduled_daily_report, 
                'cron', 
                hour=9, 
                minute=0,
                id='daily_report_job'
            )
        
        # Self-test (08:00)
        if self.send_selftest_report:
            scheduler.add_job(
                self.scheduled_selftest, 
                'cron', 
                hour=8, 
                minute=0,
                id='selftest_job'
            )
        
        # Golden test (07:00)
        if self.run_golden_test:
            scheduler.add_job(
                self.scheduled_golden_test, 
                'cron', 
                hour=7, 
                minute=0,
                id='golden_test_job'
            )
        
        # Stale flow temizliği (her saat)
        if self.cleanup_stale_flows:
            scheduler.add_job(
                self.cleanup_stale_flows, 
                'interval', 
                hours=1,
                id='stale_cleanup_job'
            )
        
        # Rezervasyon hatırlatma (her 5 dakika)
        if self.check_reservation_reminders:
            scheduler.add_job(
                self.run_reservation_reminders, 
                'interval', 
                minutes=5,
                id='reservation_reminder_job'
            )
        
        print("✅ Scheduler job'ları yapılandırıldı")
    
    # ======================================================
    # COALESCE JOB (kassandra_openai_bot.py satır 4349-4391)
    # ======================================================
    
    def check_and_flush_coalesce_buffers(self):
        """Her 2 saniyede çalışır, flush edilmesi gereken buffer'ları işler"""
        if not self.coalescer or not hasattr(self.coalescer, 'coalesce_is_enabled'):
            return
        
        if not self.coalescer.coalesce_is_enabled():
            return
        
        now = time_module.time()
        phones_to_flush = []
        
        # Flush edilecekleri bul
        try:
            with self.coalescer.MESSAGE_COALESCER._lock:
                for phone, buffer in list(self.coalescer.MESSAGE_COALESCER._buffers.items()):
                    if buffer.is_processing:
                        continue
                    
                    silence = now - buffer.last_message_time
                    total_wait = now - buffer.first_message_time
                    
                    # Sessizlik veya toplam bekleme aşıldı
                    if silence >= self.coalesce_window_seconds or total_wait >= self.max_coalesce_wait_seconds:
                        phones_to_flush.append(phone)
        except Exception as e:
            print(f"❌ Coalesce buffer check hatası: {e}")
            return
        
        # Flush işlemlerini yap
        for phone in phones_to_flush:
            try:
                flush_result = self.coalescer.MESSAGE_COALESCER.flush(phone)
                if flush_result["has_messages"]:
                    merged_text = flush_result["merged_text"]
                    print(f"🔄 COALESCE FLUSH: {phone[:6]}*** - {flush_result['message_count']} mesaj birleştirildi")
                    
                    if self.process_coalesced_message:
                        run_async_job(lambda: self.process_coalesced_message(phone, merged_text))
                    
                    self.coalescer.MESSAGE_COALESCER.complete_processing(phone)
            except Exception as e:
                print(f"❌ Coalesce flush hatası ({phone}): {e}")
                try:
                    self.coalescer.MESSAGE_COALESCER.complete_processing(phone)
                except:
                    pass
    
    # ======================================================
    # GÜNLÜK RAPOR (kassandra_openai_bot.py satır 4444-4454)
    # ======================================================
    
    def scheduled_daily_report(self):
        """Zamanlı günlük rapor"""
        if not self.send_daily_report:
            return
        
        try:
            run_async_job(self.send_daily_report)
            print("📊 Zamanlanmış günlük rapor gönderildi")
        except Exception as e:
            print(f"❌ Günlük rapor hatası: {e}")
    
    # ======================================================
    # SELF-TEST (kassandra_openai_bot.py satır 4456-4466)
    # ======================================================
    
    def scheduled_selftest(self):
        """Zamanlı self-test"""
        if not self.send_selftest_report:
            return
        
        try:
            run_async_job(self.send_selftest_report)
            print("🧪 Zamanlanmış self-test tamamlandı")
        except Exception as e:
            print(f"❌ Self-test hatası: {e}")
    
    # ======================================================
    # GOLDEN TEST (kassandra_openai_bot.py satır 4559-4587)
    # ======================================================
    
    def scheduled_golden_test(self):
        """Günlük golden scenarios testi çalıştır"""
        if not self.run_golden_test:
            return
        
        print("🧪 Günlük Golden Test başlatılıyor...")
        
        try:
            async def run_test():
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "http://127.0.0.1:8000/admin/test/golden?notify=true",
                        timeout=120
                    )
                    return response.json()
            
            result = None
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(run_test())
                print(f"🧪 Golden Test tamamlandı: {result.get('passed', 0)}/{result.get('total', 0)} PASS")
            finally:
                loop.close()
                
        except Exception as e:
            print(f"❌ Golden Test hatası: {e}")
    
    # ======================================================
    # REZERVASYON HATIRLATMA (kassandra_openai_bot.py satır 4540-4556)
    # ======================================================
    
    def run_reservation_reminders(self):
        """Sync wrapper for async reminder check"""
        if not self.check_reservation_reminders:
            return
        
        try:
            run_async_job(self.check_reservation_reminders)
        except Exception as e:
            print(f"❌ Reminder scheduler hatası: {e}")
    
    # ======================================================
    # STARTUP/SHUTDOWN
    # ======================================================
    
    def start(self):
        """Scheduler'ı başlat"""
        if self._scheduler:
            self._scheduler.start()
            print("✅ Scheduler başlatıldı:")
            print("   🧪 Golden Test: Her gün 07:00")
            print("   🧪 Self-test: Her gün 08:00")
            print("   📊 Günlük rapor: Her gün 09:00")
            print("   🧹 Stale flow temizliği: Her 1 saatte")
            print("   📨 Rezervasyon hatırlatma: Her 5 dakikada")
    
    def stop(self):
        """Scheduler'ı durdur"""
        if self._scheduler:
            self._scheduler.shutdown()
            print("🛑 Scheduler durduruldu")


# ======================================================
# SINGLETON
# ======================================================

_scheduler_service: Optional[SchedulerService] = None

def get_scheduler_service(**kwargs) -> SchedulerService:
    """Singleton scheduler service döndür"""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService(**kwargs)
    return _scheduler_service


# ======================================================
# REZERVASYON HATIRLATMA FONKSİYONU (kassandra_openai_bot.py satır 4478-4538)
# ======================================================

async def check_reservation_flow_reminders(
    load_reservation_flows: Callable,
    save_reservation_flows: Callable,
    send_whatsapp_message: Callable
):
    """
    5 dakikadır cevap vermeyen müşterilere TEK bir hatırlatma gönder.
    Hatırlatma gönderildikten sonra akışı kapat.
    """
    try:
        flows = load_reservation_flows()
        if not flows:
            return
        
        now = datetime.now()
        phones_to_remind = []
        
        for phone, flow in flows.items():
            # Zaten hatırlatma gönderilmiş mi?
            if flow.get("reminder_sent", False):
                continue
            
            # Son aktivite zamanını kontrol et
            last_activity_str = flow.get("last_activity_at")
            if not last_activity_str:
                continue
            
            try:
                last_activity = datetime.fromisoformat(last_activity_str)
                minutes_elapsed = (now - last_activity).total_seconds() / 60
                
                # 5 dakikadan fazla geçmiş
                if minutes_elapsed >= 5:
                    phones_to_remind.append((phone, flow))
            except:
                continue
        
        # Hatırlatma gönder
        for phone, flow in phones_to_remind:
            lang = flow.get("data", {}).get("language", "tr")
            
            # Duruma göre hatırlatma mesajı
            if lang == "en":
                reminder_msg = "Hi! I noticed we were in the middle of making a reservation. Would you like to continue? If you need any help, just let me know! 😊"
            else:
                reminder_msg = "Merhaba! Rezervasyon işleminiz yarım kaldı. Devam etmek ister misiniz? Yardıma ihtiyacınız olursa bana yazabilirsiniz! 😊"
            
            try:
                await send_whatsapp_message(phone, reminder_msg)
                print(f"📨 Rezervasyon hatırlatması gönderildi: {phone[:6]}***")
                
                # Hatırlatma gönderildi olarak işaretle ve akışı kapat
                flows = load_reservation_flows()
                if phone in flows:
                    del flows[phone]
                    save_reservation_flows(flows)
                    
            except Exception as e:
                print(f"❌ Hatırlatma gönderme hatası ({phone}): {e}")
                
    except Exception as e:
        print(f"❌ Reservation reminder check hatası: {e}")
