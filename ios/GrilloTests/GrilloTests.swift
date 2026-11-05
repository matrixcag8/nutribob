import Foundation
import Testing
@testable import Grillo

@Test func foodsLoadAndScale() throws {
    #expect(Food.all.count > 300)
    let mela = try #require(Food.all.first { $0.name == "mela" })
    let entry = Entry(food: mela, grams: 200)
    #expect(entry.kcal == mela.kcal * 2)
    #expect(entry.carbs == mela.carbs.map { $0 * 2 })
}

@Test func targetMifflinStJeor() {
    var p = Profile(sex: .uomo, age: 30, height: 180, weight: 80, activity: .moderato, goal: .mantenere)
    #expect(p.bmr == 1780)
    #expect(Int(p.tdee) == 2759)
    p.goal = .dimagrire
    #expect(Int(p.target) == 2259)
    p.activity = .sedentario
    p.goal = .dimagrire
    #expect(p.target >= p.bmr)  // il taglio non scende sotto il basale
}

@Test func reminderOnlyWhenOffThreshold() {
    var p = Profile(goal: .aumentare, threshold: 1500)
    #expect(Reminder.message(p, kcal: 1000) != nil)
    #expect(Reminder.message(p, kcal: 1600) == nil)
    p.goal = .dimagrire
    #expect(Reminder.message(p, kcal: 1000) == nil)
    #expect(Reminder.message(p, kcal: 1600) != nil)
    p.goal = .mantenere
    #expect(Reminder.message(p, kcal: 0) == nil)
}

@Test func stripsQwenThinking() {
    #expect(Grillo.stripThinking("<think>\n\n</think>\n\nCiao!") == "Ciao!")
}

@Test func streakAndWeek() {
    let mela = Food.all.first { $0.name == "mela" }!
    let day: (Int) -> Date = { .now.addingTimeInterval(Double(-$0) * 86400) }
    let entries = [Entry(food: mela, grams: 100, date: day(1)), Entry(food: mela, grams: 100, date: day(2)),
                   Entry(food: mela, grams: 100, date: day(4))]
    #expect(HomeView.streak(entries) == 2)  // oggi vuoto non rompe, il buco al giorno 3 sì
    let week = HomeView.lastDays(7, entries)
    #expect(week.count == 7)
    #expect(week.last!.kcal == 0)
    #expect(week[5].kcal == mela.kcal)
}

@Test func microsScaleWithGrams() throws {
    let spinaci = try #require(Food.byName["spinaci"])
    let entry = Entry(food: spinaci, grams: 200)
    #expect(entry.micros?[.iron] == spinaci.micros!["iron"]! * 2)
    #expect(Entry(food: Food.byName["pasta carbonara"]!, grams: 100).micros == nil)  // piatto composto: niente dati
    #expect(Food.all.filter { $0.micros != nil }.count > 300)
}

@Test func oldProfileKeepsDataWithoutMeals() throws {
    let old = #"{"sex":"donna","age":40,"height":165,"weight":60,"activity":1.55,"goal":"dimagrire","checkHour":18}"#
    let p = Profile.decode(Data(old.utf8))
    #expect(p.age == 40 && p.sex == .donna)  // non ricade sul profilo di default
    #expect(p.mealCount == 3)
}

@Test func mealSlotsFixedPlusOneMore() {
    #expect(MealSlots.options(fixed: 3, used: []) == [1, 2, 3])
    #expect(MealSlots.options(fixed: 3, used: [1, 3]) == [1, 2, 3, 4])  // dopo l'ultimo fisso se ne può aprire uno nuovo
    #expect(MealSlots.options(fixed: 1, used: [1, 2]) == [1, 2, 3])
}

@Test func analysisPromptHasMealsAndStatus() throws {
    let day = [Entry(food: Food.byName["spinaci"]!, grams: 100, meal: 1),
               Entry(food: Food.byName["pasta carbonara"]!, grams: 100, meal: 2)]
    let prompt = Grillo.analysisPrompt(day: day, profile: Profile())
    #expect(prompt.contains("Pasto 1: spinaci 100 g"))
    #expect(prompt.contains("Pasto 2: pasta carbonara 100 g"))
    #expect(prompt.contains("vitamina D: 0.0 µg, 0% del riferimento (SCARSO)"))
    #expect(prompt.contains("non contati: pasta carbonara"))
}
