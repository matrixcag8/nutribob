import SwiftUI
import SwiftData

@main
struct GrilloApp: App {
    var body: some Scene {
        WindowGroup { RootView() }
            .modelContainer(for: [Entry.self, DayAnalysis.self])
    }
}

private enum TabID: Hashable { case home, diary, add, profile }

/// Barra in basso stile social: il + al centro apre l'aggiunta invece di cambiare tab.
struct RootView: View {
    @State private var tab = TabID.home
    @State private var adding = false
    @AppStorage("profile") private var profileData: Data?
    @Query private var entries: [Entry]

    private var todayKcal: Double {
        entries.filter { Calendar.current.isDateInToday($0.date) }.reduce(0) { $0 + $1.kcal }
    }

    var body: some View {
        TabView(selection: $tab) {
            Tab("Home", systemImage: "house.fill", value: .home) { HomeView() }
            Tab("Diario", systemImage: "book.fill", value: .diary) { DiaryView() }
            Tab("Aggiungi", systemImage: "plus.circle.fill", value: .add) { Color.clear }
            Tab("Profilo", systemImage: "person.fill", value: .profile) { NavigationStack { SettingsView() } }
        }
        .tint(.green)
        .onChange(of: tab) { old, new in
            if new == .add { adding = true; tab = old }
        }
        .sheet(isPresented: $adding) { AddFoodView() }
        .fullScreenCover(isPresented: .constant(profileData == nil)) { OnboardingView() }
        .task(id: "\(Int(todayKcal))-\(profileData?.hashValue ?? 0)") { await Reminder.update(todayKcal: todayKcal) }
    }
}
