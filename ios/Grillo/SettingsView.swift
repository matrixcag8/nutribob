import SwiftUI
import SwiftData

struct SettingsView: View {
    @AppStorage("tone") private var tone = Tone.gentile
    @State private var profile = Profile.current
    @AppStorage("profile") private var profileData: Data?
    @Environment(\.modelContext) private var context
    @State private var confirmReset = false

    var body: some View {
        Form {
            Picker("Carattere del grillo", selection: $tone) {
                ForEach(Tone.allCases) { Text($0.rawValue.capitalized).tag($0) }
            }
            .pickerStyle(.inline)
            NavigationLink("Come funziona il grillo") { GuideView() }
            Section {
                Stepper("Pasti al giorno: \(profile.mealCount)", value: Binding(get: { profile.mealCount }, set: { profile.meals = $0 }), in: 1...8)
            } header: { Text("Pasti") } footer: {
                Text("Nel diario di oggi trovi sempre questi pasti. Se ne fai uno in più, lo aggiungi quando segni un alimento.")
            }
            ProfileForm(profile: $profile)
            Section("Fonti") {
                Text("Calorie e macro per 100 g dalle tabelle di NutriBob. \"n.d.\" = macro non ancora disponibili. "
                     + "Micronutrienti dalle tabelle USDA FoodData Central (SR Legacy); i piatti composti non li hanno. "
                     + "Riferimenti giornalieri: LARN 2014 per adulti.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section {
                Button("Azzera tutti i dati", role: .destructive) { confirmReset = true }
            } footer: {
                Text("Cancella diario, analisi e profilo. Il cervello del grillo scaricato resta.")
            }
        }
        .confirmationDialog("Cancellare tutto? Non si può annullare.", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Azzera tutto", role: .destructive, action: reset)
        }
        .dismissableKeyboard()
        .onChange(of: profile.goal) { profile.threshold = nil }
        .onChange(of: profile) { profile.save() }
        // dopo l'onboarding (anche post-reset) ricarica il profilo nuovo, sennò il form risalverebbe quello vecchio
        .onChange(of: profileData) { if let profileData { profile = Profile.decode(profileData) } }
        .navigationTitle("Profilo")
    }

    private func reset() {
        try? context.delete(model: Entry.self)
        try? context.delete(model: DayAnalysis.self)
        try? context.save()
        UserDefaults.standard.removeObject(forKey: "tone")
        profileData = nil  // riapre l'onboarding
    }
}

/// Indicazioni d'uso del grillo.
private struct GuideView: View {
    var body: some View {
        List {
            Section("Cosa fa") {
                Text("Il grillo è la tua coscienza alimentare: non ti dà diete, ti fa ragionare sulle scelte rispetto al tuo obiettivo. Funziona sul telefono, senza internet, e i tuoi dati non escono dall'app.")
            }
            Section("Analisi della giornata") {
                Text("A fine giornata, nel diario, tocca \"Analizza la giornata\". Il grillo guarda tutti i pasti e ti parla di:")
                Label("bilancio di calorie e proteine e come le hai distribuite tra i pasti", systemImage: "chart.pie")
                Label("micronutrienti scarsi o oltre il limite (fibre, ferro, calcio, vitamine, sodio, zuccheri…) e da quali alimenti arrivano", systemImage: "leaf")
                Label("combinazioni nello stesso pasto, per esempio ferro con vitamina C o legumi con cereali", systemImage: "fork.knife")
                Text("Più il diario è completo, più l'analisi è utile. Puoi rifarla se aggiungi qualcosa.")
            }
            Section("Pasti") {
                Text("Nel profilo scegli quanti pasti fai al giorno: il diario di oggi te li mostra sempre, e con + aggiungi un alimento proprio a quel pasto. Se fai un pasto in più, lo scegli quando segni l'alimento.")
            }
            Section("Limiti") {
                Text("I conti li fa l'app, il grillo li commenta: può comunque sbagliare. I micronutrienti mancano per i piatti composti (es. carbonara, tiramisù) e sono valori medi. Non è un consiglio medico: per esigenze particolari senti un professionista.")
            }
        }
        .navigationTitle("Come funziona")
    }
}
