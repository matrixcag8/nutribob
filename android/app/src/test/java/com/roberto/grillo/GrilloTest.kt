package com.roberto.grillo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime

class GrilloTest {
    private val foods = Food.parse(File("src/main/assets/foods.json").readText())
    private val mela = foods.first { it.name == "mela" }

    @Test fun foodsLoadAndScale() {
        assertTrue(foods.size > 300)
        val e = Entry(mela, 200.0)
        assertEquals(mela.kcal * 2, e.kcal, 1e-9)
        assertEquals(mela.carbs!! * 2, e.carbs!!, 1e-9)
    }

    @Test fun entryJsonRoundTrip() {
        val e = Entry(foods.first { it.protein == null }, 120.0).copy(comment = "ciao")
        assertEquals(e, Entry.fromJson(org.json.JSONObject(e.toJson().toString())))
    }

    @Test fun promptHasTodayOnly() {
        val old = Entry(mela, 100.0, LocalDateTime.now().minusDays(3))
        val now = Entry(mela, 150.0)
        val prompt = Grillo.prompt(now, listOf(old, now), Profile())
        val todaySection = prompt.split("Calorie degli ultimi")[0]
        assertEquals(2, todaySection.split("\n- ").size)  // solo la voce di oggi
        assertTrue(prompt.contains("150 g"))
    }

    @Test fun targetMifflinStJeor() {
        var p = Profile(Sex.uomo, 30, 180.0, 80.0, Activity.moderato, Goal.mantenere)
        assertEquals(1780.0, p.bmr, 1e-9)
        assertEquals(2759, p.tdee.toInt())
        p = p.copy(goal = Goal.dimagrire)
        assertEquals(2259, p.target.toInt())
        p = p.copy(activity = Activity.sedentario)
        assertTrue(p.target >= p.bmr)  // il taglio non scende sotto il basale
    }

    @Test fun reminderOnlyWhenOffThreshold() {
        var p = Profile(goal = Goal.aumentare, threshold = 1500.0)
        assertNotNull(Reminder.message(p, 1000.0))
        assertNull(Reminder.message(p, 1600.0))
        p = p.copy(goal = Goal.dimagrire)
        assertNull(Reminder.message(p, 1000.0))
        assertNotNull(Reminder.message(p, 1600.0))
        p = p.copy(goal = Goal.mantenere)
        assertNull(Reminder.message(p, 0.0))
    }

    @Test fun stripsQwenThinking() {
        assertEquals("Ciao!", Grillo.stripThinking("<think>\n\n</think>\n\nCiao!"))
    }

    @Test fun streakAndWeek() {
        val day = { n: Long -> LocalDateTime.now().minusDays(n) }
        val entries = listOf(Entry(mela, 100.0, day(1)), Entry(mela, 100.0, day(2)), Entry(mela, 100.0, day(4)))
        assertEquals(2, streak(entries))  // oggi vuoto non rompe, il buco al giorno 3 sì
        val week = lastDays(7, entries)
        assertEquals(7, week.size)
        assertEquals(LocalDate.now(), week.last().first)
        assertEquals(0.0, week.last().second, 0.0)
        assertEquals(mela.kcal, week[5].second, 1e-9)
    }
}
