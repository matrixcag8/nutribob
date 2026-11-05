package com.roberto.grillo

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.app.Notification
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

/**
 * Il grillo ti richiama all'ora del controllo se sei fuori soglia rispetto all'obiettivo.
 * A differenza di iOS il messaggio si calcola quando scatta l'allarme, con le kcal reali di quel momento.
 */
object Reminder {
    fun message(profile: Profile, kcal: Double): String? {
        val soglia = profile.effectiveThreshold.toInt()
        val k = kcal.toInt()
        val ora = profile.checkHour
        return when {
            profile.goal == Goal.aumentare && kcal < profile.effectiveThreshold ->
                if (k == 0) "Sono le $ora e non hai ancora segnato niente. Per salire di peso a quest'ora dovresti essere ad almeno $soglia kcal: cosa mangi adesso?"
                else "Sono le $ora e sei a $k kcal, sotto le $soglia che ti servono a quest'ora per salire. Cosa ci metti adesso?"
            profile.goal == Goal.dimagrire && kcal > profile.effectiveThreshold ->
                "Sono le $ora e sei già a $k kcal, oltre la soglia di $soglia. Come imposti il resto della giornata?"
            else -> null
        }
    }

    /** Pianifica il prossimo controllo (oggi se l'ora non è passata, altrimenti domani). */
    fun schedule(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java)
        val pi = PendingIntent.getBroadcast(ctx, 0, Intent(ctx, ReminderReceiver::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val profile = Store.profile
        if (profile == null || profile.goal == Goal.mantenere) { am.cancel(pi); return }
        var fire = LocalDate.now().atTime(profile.checkHour, 0)
        if (fire <= LocalDateTime.now()) fire = fire.plusDays(1)
        val ms = fire.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        // inesatto (finestra di 10 min): gli allarmi esatti richiedono un permesso speciale da Android 12
        am.setWindow(AlarmManager.RTC_WAKEUP, ms, 10 * 60_000L, pi)
    }
}

/** Scatta all'ora del controllo e al riavvio del telefono (che cancella gli allarmi). */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        Store.init(ctx)
        Reminder.schedule(ctx)
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) return
        val text = Store.profile?.let { Reminder.message(it, Store.todayKcal()) } ?: return
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("check", "Controllo giornaliero", NotificationManager.IMPORTANCE_DEFAULT))
        val open = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        nm.notify(1, Notification.Builder(ctx, "check")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Il grillo")
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build())
    }
}
