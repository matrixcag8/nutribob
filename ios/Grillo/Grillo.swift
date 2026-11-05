import Foundation
import FoundationModels
import HuggingFace
import MLXHuggingFace
import MLXLLM
import MLXLMCommon
import Tokenizers

/// Il grillo parlante: analizza la giornata con un modello on-device.
/// Usa Apple Intelligence se c'è, altrimenti Qwen3 1.7B scaricato nell'app.
enum Grillo {
    static var hasAppleModel: Bool { SystemLanguageModel.default.isAvailable }

    static func analysisInstructions(_ tone: Tone) -> String {
        let voice = switch tone {
        case .gentile: "Tono gentile e incoraggiante."
        case .diretto: "Tono diretto e franco, mai offensivo."
        }
        return """
        Sei il Grillo Parlante, la coscienza alimentare dell'utente. Rispondi in italiano. \
        Analizza la giornata in tre parti brevi con questi titoli: "Bilancio", "Micronutrienti", "Combinazioni". \
        Bilancio: calorie e proteine rispetto all'obiettivo e come sono distribuite tra i pasti. \
        Micronutrienti: commenta solo quelli segnati SCARSO o OLTRE IL LIMITE, citando gli alimenti indicati. \
        Combinazioni: guarda gli alimenti di ogni pasto e usa solo queste regole: \
        il ferro di vegetali e legumi si assorbe meglio con vitamina C nello stesso pasto; \
        latticini nello stesso pasto riducono l'assorbimento del ferro; tè e caffè ai pasti riducono il ferro; \
        carboidrati insieme a proteine, fibre o grassi danno un picco di zucchero nel sangue più basso; \
        legumi e cereali insieme danno proteine complete; vitamine A e D si assorbono meglio con un po' di grassi. \
        Chiudi con un solo suggerimento pratico per domani. Usa solo i numeri forniti, non inventarne. \
        Massimo 180 parole. Non dare consigli medici. \(voice)
        """
    }

    /// I conti (totali, percentuali, chi fornisce cosa) li fa il codice: il modello piccolo commenta e basta.
    static func analysisPrompt(day: [Entry], profile: Profile) -> String {
        let sum = { (items: [Entry], m: Micro) in items.reduce(0) { $0 + ($1.micros?[m] ?? 0) } }
        let meals = Dictionary(grouping: day) { $0.meal ?? 0 }.sorted { $0.key < $1.key }.map { meal, items in
            let foods = items.map { "\($0.name) \($0.grams.g)" }.joined(separator: ", ")
            return "- \(meal == 0 ? "Senza pasto" : "Pasto \(meal)"): \(foods). \(Int(items.reduce(0) { $0 + $1.kcal })) kcal, "
                + "ferro \(fmt(sum(items, .iron))) mg, vitamina C \(fmt(sum(items, .vitC))) mg, calcio \(fmt(sum(items, .calcium))) mg"
        }
        let microLines = Micro.allCases.map { m in
            let pct = Int(sum(day, m) / m.reference(profile) * 100)
            let status = m.isLimit ? (pct > 100 ? "OLTRE IL LIMITE" : "entro il limite")
                : (pct < 50 ? "SCARSO" : pct < 90 ? "un po' basso" : "ok")
            let top = day.compactMap { e in e.micros?[m].map { (e.name, $0) } }.filter { $0.1 > 0 }
                .sorted { $0.1 > $1.1 }.prefix(2).map(\.0)
            return "- \(m.label): \(fmt(sum(day, m))) \(m.unit), \(pct)% del riferimento (\(status))"
                + (top.isEmpty ? "" : ", soprattutto da \(top.joined(separator: " e "))")
        }
        let unknown = day.filter { $0.micros == nil }.map(\.name)
        return """
        Obiettivo: \(profile.goal.rawValue) di peso. Target \(Int(profile.target)) kcal, proteine \(Int(profile.protein)) g.
        Totale della giornata: \(Int(day.reduce(0) { $0 + $1.kcal })) kcal, proteine \(Int(day.reduce(0) { $0 + ($1.protein ?? 0) })) g.
        Pasti:
        \(meals.joined(separator: "\n"))
        Micronutrienti della giornata:
        \(microLines.joined(separator: "\n"))
        \(unknown.isEmpty ? "" : "Senza dati sui micronutrienti, non contati: \(unknown.joined(separator: ", ")).")
        """
    }

    static func analyze(day: [Entry], tone: Tone) async -> String? {
        await respond(analysisInstructions(tone), analysisPrompt(day: day, profile: .current), maxTokens: 600)
    }

    static func fmt(_ v: Double) -> String { v < 10 ? String(format: "%.1f", v) : "\(Int(v.rounded()))" }

    private static func respond(_ instructions: String, _ prompt: String, maxTokens: Int) async -> String? {
        if hasAppleModel {
            let session = LanguageModelSession(instructions: instructions)
            return try? await session.respond(to: prompt).content
        }
        guard let container = await LocalModel.shared.loaded() else { return nil }
        let session = ChatSession(container, instructions: instructions,
                                  generateParameters: .init(maxTokens: maxTokens, temperature: 0.7),
                                  additionalContext: ["enable_thinking": false])
        return (try? await session.respond(to: prompt)).map(stripThinking)
    }

    /// Qwen3 può lasciare un blocco <think></think> vuoto anche col ragionamento spento.
    static func stripThinking(_ text: String) -> String {
        text.replacingOccurrences(of: #"<think>[\s\S]*?</think>"#, with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// Qwen3 1.7B (4 bit, ~1 GB): si scarica una volta da Hugging Face, poi gira offline.
@MainActor @Observable final class LocalModel {
    static let shared = LocalModel()

    var progress: Double?  // non nil durante download/caricamento
    var error: String?
    private(set) var downloaded = UserDefaults.standard.bool(forKey: "modelDownloaded")
    private var container: ModelContainer?

    /// Carica il modello solo se è già stato scaricato (non avvia download da 1 GB a sorpresa).
    func loaded() async -> ModelContainer? {
        if container == nil, downloaded { await load() }
        return container
    }

    func load() async {
        guard container == nil, progress == nil else { return }
        progress = 0
        error = nil
        do {
            // etichetta obbligatoria: la macro ignora la trailing closure e la barra resterebbe a 0
            container = try await #huggingFaceLoadModelContainer(
                configuration: LLMRegistry.qwen3_1_7b_4bit,
                progressHandler: { p in
                    Task { @MainActor in LocalModel.shared.progress = p.fractionCompleted }
                })
            downloaded = true
            UserDefaults.standard.set(true, forKey: "modelDownloaded")
        } catch {
            self.error = error.localizedDescription
        }
        progress = nil
    }
}
