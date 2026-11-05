import SwiftUI
import UserNotifications

/// Dati e obiettivi dell'utente: usato al primo avvio e nelle impostazioni.
struct ProfileForm: View {
    @Binding var profile: Profile

    var body: some View {
        Section("Chi sei") {
            Picker("Sesso", selection: $profile.sex) {
                ForEach(Sex.allCases) { Text($0.rawValue.capitalized).tag($0) }
            }
            .pickerStyle(.segmented)
            Stepper("Età: \(profile.age) anni", value: $profile.age, in: 14...100)
            LabeledContent("Altezza (cm)") {
                TextField("cm", value: $profile.height, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
            }
            LabeledContent("Peso (kg)") {
                TextField("kg", value: $profile.weight, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
            }
            Picker("Attività", selection: $profile.activity) {
                ForEach(Activity.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.navigationLink)
        }
        Section {
            Picker("Obiettivo", selection: $profile.goal) {
                ForEach(Goal.allCases) { Text($0.rawValue.capitalized).tag($0) }
            }
            .pickerStyle(.segmented)
            LabeledContent("Calorie al giorno", value: "\(Int(profile.target)) kcal")
            LabeledContent("Proteine al giorno", value: "\(Int(profile.protein)) g")
        } header: {
            Text("Obiettivo")
        } footer: {
            Text("Stima con la formula di Mifflin-St Jeor: è un punto di partenza, non una prescrizione.")
        }
        if profile.goal != .mantenere {
            Section {
                Stepper("Controllo alle \(profile.checkHour):00", value: $profile.checkHour, in: 8...22)
                LabeledContent("Soglia (kcal)") {
                    TextField("kcal", value: Binding(get: { profile.effectiveThreshold }, set: { profile.threshold = $0 }),
                              format: .number)
                        .keyboardType(.numberPad).multilineTextAlignment(.trailing)
                }
            } header: {
                Text("Il grillo ti richiama")
            } footer: {
                Text(profile.goal == .aumentare
                     ? "Se a quell'ora sei sotto la soglia, ti arriva una notifica."
                     : "Se a quell'ora hai già superato la soglia, ti arriva una notifica.")
            }
        }
    }
}

struct OnboardingView: View {
    @State private var profile = Profile()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Ciao, sono il grillo. Prima di cominciare dimmi qualcosa di te e cosa vuoi ottenere: così so quando richiamarti.")
                }
                ProfileForm(profile: $profile)
            }
            .dismissableKeyboard()
            .onChange(of: profile.goal) { profile.threshold = nil }
            .navigationTitle("I tuoi obiettivi")
            .toolbar {
                Button("Inizia") {
                    profile.save()
                    Task { _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) }
                }
                .disabled(profile.height < 100 || profile.weight < 30)
            }
        }
    }
}

extension View {
    /// Il tastierino numerico non ha Invio: freccia gialla sopra la tastiera e trascinamento per chiuderla.
    func dismissableKeyboard() -> some View {
        scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button {
                        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                    } label: {
                        Image(systemName: "chevron.down").fontWeight(.bold).foregroundStyle(.yellow)
                    }
                    .accessibilityLabel("Chiudi tastiera")
                }
            }
    }
}
