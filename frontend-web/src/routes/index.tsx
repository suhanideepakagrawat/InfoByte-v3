import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import {
  Search, Cloud, Newspaper, BookOpen, MessageSquare, Code2, ArrowUpRight,
  ChevronDown, Sparkles, Timer, Radar, Wind, Droplets, Thermometer, ArrowUp, Check, Globe, Database, Salad, Scale, Loader2,
  Activity, AlertTriangle, Info
} from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "InfoByte Engine — Cross-Source Routing Intelligence" },
      { name: "description", content: "A minimalist AI search that classifies intent and unifies results." },
    ],
  }),
  component: SearchView,
});

const API_BASE = "http://127.0.0.1:8000/api";

const ALL_TAXONOMY_INTENTS = [
  "technical_code", "technical_oracle", "discussion_social",
  "general_wiki", "movies", "weather", "google_search", "academic_research", "medical_research", "medicine", "food_nutrition"
];

const INTENT_DISPLAY_NAMES: Record<string, string> = {
  technical_code: "Technical Code",
  technical_oracle: "Technical Oracle",
  discussion_social: "Social Discussion",
  general_wiki: "General Wiki",
  movies: "Movies",
  weather: "Weather",
  google_search: "Google Search",
  academic_research: "Academic Research",
  medical_research: "Medical Research",
  medicine: "Medicine",
  food_nutrition: "Food & Nutrition"
};

interface MedicineIngredient {
  name?: string | null;
  strength?: string | null;
}

interface MedicineIngredients {
  active?: MedicineIngredient[] | null;
  inactive?: MedicineIngredient[] | null;
  source?: string | null;
}

interface MedicineIngredientLabel {
  ingredient?: string | null;
  query?: string | null;
  openfda?: any;
  dailymed?: any;
  medicine?: MedicineData | null;
  errors?: Record<string, string>;
}

interface MedicineData {
  medicine_name?: string | null;
  brand_name?: string | null;
  generic_name?: string | null;
  name?: string | null;
  manufacturer?: string | null;
  route?: string | null;
  active_ingredients?: any;
  ingredients?: MedicineIngredients | null;
  uses?: any;
  dosage?: any;
  side_effects?: any;
  warnings?: any;
  precautions?: string | null;
  official_label_url?: string | null;
  official_label?: {
    source?: string | null;
    url?: string | null;
    dailymed_set_id?: string | null;
  } | null;
  ingredient_labels?: MedicineIngredientLabel[] | null;
  combination_label_notice?: string | null;
  product_type?: string | null;
  structured_sections?: {
    uses?: { title?: string; items?: string[] };
    dosage?: { title?: string; raw_text?: string | null; facts?: Record<string, string | null> };
    side_effects?: { title?: string; items?: string[] };
    warnings?: { title?: string; raw_text?: string | null };
    precautions?: { title?: string; raw_text?: string | null };
  } | null;
  error?: string | null;
}

interface NutritionPortion {
  description?: string | null;
  gram_weight?: number | null;
  unit?: string | null;
  modifier?: string | number | null;
  amount?: string | number | null;
}

interface NutritionData {
  [key: string]: unknown;
  food_name?: string;
  description?: string;
  food_category?: string;
  data_type?: string;
  brand_owner?: string;
  fdc_id?: number | string;
  nutrients?: Record<string, unknown>;
  nutrient_basis?: { display?: string } | string;
  requested_portion?: { display?: string; label?: string; amount?: number } | null;
  requested_portion_nutrients?: Record<string, unknown>;
  usda_defined_portions?: NutritionPortion[];
  alternative_matches?: Array<Record<string, unknown>>;
  error?: string | null;
}

function normalizeNutritionPayload(data: unknown): NutritionData | null {
  if (!data || typeof data !== "object") return null;

  const dataRecord = data as Record<string, any>;
  const candidatePaths = [
    data,
    dataRecord.payload,
    dataRecord.payload?.nutrition,
    dataRecord.payload?.nutrition?.payload,
    dataRecord.payload?.nutrition?.nutrition,
    dataRecord.payload?.nutrition?.payload?.nutrition,
    dataRecord.display_payload,
    dataRecord.display_payload?.nutrition,
    dataRecord.display_payload?.nutrition?.payload,
    dataRecord.display_payload?.nutrition?.nutrition,
  ];

  for (const candidate of candidatePaths) {
    if (candidate && typeof candidate === "object") {
      if (
        (candidate as Record<string, unknown>).nutrients ||
        (candidate as Record<string, unknown>).food_name ||
        (candidate as Record<string, unknown>).fdc_id ||
        (candidate as Record<string, unknown>).nutrient_basis
      ) {
        return candidate as NutritionData;
      }

      if (
        (candidate as Record<string, unknown>).nutrition &&
        typeof (candidate as Record<string, unknown>).nutrition === "object"
      ) {
        return (candidate as Record<string, unknown>).nutrition as NutritionData;
      }
    }
  }

  return data as NutritionData;
}

function SearchView() {
  const [query, setQuery] = useState("");
  const [isClassifying, setIsClassifying] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [searchStage, setSearchStage] = useState<"input" | "verify_intent" | "display_results">("input");
  
  const [classification, setClassification] = useState<any>(null);
  const [initialSummary, setInitialSummary] = useState<string | null>(null);
  const [chosenIntent, setChosenIntent] = useState<string>("");
  const [results, setResults] = useState<any>(null);
  const [latency, setLatency] = useState<number>(0);
  const [openContracts, setOpenContracts] = useState<Record<string, boolean>>({});
  
  const [selectedWikiTitle, setSelectedWikiTitle] = useState<string | null>(null);
  const [selectedWikiContent, setSelectedWikiContent] = useState<string | null>(null);
  const [isReSynthesizingWiki, setIsReSynthesizingWiki] = useState<boolean>(false);

  const toggle = (k: string) => setOpenContracts((s) => ({ ...s, [k]: !s[k] }));

  const medicalResearchData = results?.payload?.medical_research ?? results?.medical_research;
  
  // The backend now returns structured data at the root if it's the top intent, 
  // or inside formatted_data if it's a secondary intent.
  const isStructuredRoot = !!results?.cards;
  const medicineSourceData = results?.payload?.medicine ?? results?.medicine;
  
  const medicineData = isStructuredRoot 
    ? results 
    : (medicineSourceData?.payload?.formatted_data ?? medicineSourceData);

  const nutritionSourceData =
    results?.payload?.nutrition ??
    results?.payload?.food_nutrition ??
    results?.nutrition ??
    results?.food_nutrition;

  const nutritionData: NutritionData | null = normalizeNutritionPayload(nutritionSourceData);

  const handleClassify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsClassifying(true);
    setResults(null);
    setInitialSummary(null);
    setSelectedWikiTitle(null);
    setSelectedWikiContent(null);
    setSearchStage("input");

    try {
      const [classRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/classify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) }),
        fetch(`${API_BASE}/quick-summary`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) })
      ]);

      const classData = await classRes.json();
      const summaryData = await summaryRes.json();

      if (classData.error) throw new Error(classData.error);
      
      setClassification(classData);
      setChosenIntent(classData.top_intent);
      setInitialSummary(summaryData.summary);
      setSearchStage("verify_intent");
    } catch (err: any) {
      toast.error(`Classification engine failed: ${err.message}`);
    } finally {
      setIsClassifying(false);
    }
  };

  const handleConfirmAndScrape = async () => {
    const startTime = performance.now();
    setIsSearching(true);
    setIsSynthesizing(true);
    
    const topPrediction = classification?.predictions?.[0];
    const confidenceScore = topPrediction ? topPrediction.score : 1.0;
    
    fetch(`${API_BASE}/log-correction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, intent: chosenIntent, confidence: String(confidenceScore) }),
    }).catch((err) => console.error("Logging error:", err));

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, confirmed_intent: chosenIntent, skip_synthesis: true }),
      });
      const data = await res.json();
      
      if (data.error) throw new Error(data.error);

      const endTime = performance.now();
      setLatency(Number(((endTime - startTime) / 1000).toFixed(2)));
      
      setResults(data);
      setSearchStage("display_results");
      setIsSearching(false);
      
      if (data.payload && Object.keys(data.payload).length > 0) {
        const synthRes = await fetch(`${API_BASE}/synthesize`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, intent: chosenIntent, results_dict: data.payload })
        });
        
        const synthData = await synthRes.json();
        setResults((prev: any) => ({ ...prev, ai_synthesis: synthData }));
      }
    } catch (err: any) {
      toast.error(`Routing execution collapsed: ${err.message}`);
      setIsSearching(false);
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleSelectWikiArticle = async (title: string, articleUrl: string) => {
    if (!articleUrl) {
      toast.error("Wikipedia article URL is missing.");
      return;
    }

    setSelectedWikiTitle(title);
    setSelectedWikiContent(null);

    try {
      const params = new URLSearchParams({
        q: title,
        url: articleUrl,
      });

      const res = await fetch(`${API_BASE}/retriever/wiki?${params.toString()}`, {
        method: "GET",
      });

      const data = await res.json();

      if (!res.ok || data.error || data.status === "error") {
        throw new Error(
          data?.display_payload?.main_text ||
          data?.detail ||
          data?.error ||
          "Unable to fetch the selected Wikipedia article."
        );
      }

      const articlePayload = data.display_payload || {};
      const fullContent = articlePayload.main_text || "";

      if (!fullContent.trim()) {
        throw new Error("Wikipedia returned an empty article.");
      }

      setSelectedWikiTitle(articlePayload.title || title);
      setSelectedWikiContent(fullContent);
      toast.success(`Loaded complete Wikipedia article: ${articlePayload.title || title}`);
    } catch (err: any) {
      setSelectedWikiContent(null);
      toast.error(`Wikipedia article retrieval failed: ${err.message}`);
    }
  };

  const executeTargetedWikiSynthesis = async () => {
    if (!selectedWikiContent) return;
    setIsReSynthesizingWiki(true);
    toast.info("Initializing context bounding filters on selected article...");

    try {
      const mockPayload: Record<string, any> = {
        wikipedia: {
          display_payload: {
            title: selectedWikiTitle,
            main_text: selectedWikiContent
          }
        }
      };

      if (results?.payload?.google_search) {
        mockPayload["google_search"] = results.payload.google_search;
      }

      const res = await fetch(`${API_BASE}/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          intent: "general_wiki",
          results_dict: mockPayload
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      setResults((prev: any) => ({ ...prev, ai_synthesis: data }));
      toast.success("Synthesis scope refactored to targeted article selection.");
    } catch (err: any) {
      toast.error(`Targeted content summary generation failed: ${err.message}`);
    } finally {
      setIsReSynthesizingWiki(false);
    }
  };

  return (
    <AppShell>
      {isClassifying && (
        <div className="fixed inset-0 bg-background/60 backdrop-blur-md z-50 flex flex-col items-center justify-center animate-in fade-in duration-200">
          <div className="glass-card rounded-2xl p-8 max-w-sm w-full text-center flex flex-col items-center justify-center gap-4 border border-primary/30 shadow-2xl animate-in zoom-in-95 duration-300">
            <div className="relative h-16 w-16 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
              <Sparkles className="h-6 w-6 text-primary animate-pulse" />
            </div>
            <div>
              <h3 className="text-md font-bold text-foreground tracking-tight">Assembling Intelligence Vector</h3>
              <p className="text-[13px] text-muted-foreground mt-1.5 leading-relaxed">
                Please wait while InfoByte routes the intent of your query and compiles the initial AI summary data...
              </p>
            </div>
          </div>
        </div>
      )}

      <section className="text-center pt-4 pb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-white/70 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          <Sparkles className="h-3 w-3 text-primary" /> Cross-source routing engine
        </div>
        <h1 className="mt-6 text-5xl md:text-6xl leading-[1.05] tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          InfoByte <em className="italic text-primary">Engine</em>
        </h1>
        <p className="mt-4 max-w-2xl mx-auto text-[15px] text-muted-foreground leading-relaxed">
          One query, verifiable sources. InfoByte classifies user intent in real time and fulfills answers from weather feeds, news wires, encyclopedias, developer forums, and community threads.
        </p>

        <form onSubmit={handleClassify} className="mt-10 max-w-2xl mx-auto">
          <div className="glass-card rounded-2xl p-2 flex items-center gap-2 focus-within:periwinkle-glow transition-shadow">
            <div className="pl-3 text-muted-foreground"><Search className="h-5 w-5" /></div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask InfoByte anything…"
              className="flex-1 bg-transparent px-2 py-3 text-[15px] outline-none placeholder:text-muted-foreground/70"
              disabled={isClassifying || isSearching}
            />
            <button type="submit" disabled={isClassifying || isSearching} className="inline-flex items-center gap-2 gradient-primary text-white text-sm font-medium px-4 py-2.5 rounded-xl periwinkle-glow hover:brightness-105 active:brightness-95 transition disabled:opacity-50">
              {isClassifying ? "Analyzing..." : "Analyze Query Intent"}
              <ArrowUpRight className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap justify-center gap-2 text-[12px] text-muted-foreground">
            {["calories in 150g banana", "protein in 250g chicken breast", "weather in bangalore today", "ORA-00001 constraint error"].map((q) => (
              <button key={q} type="button" disabled={isClassifying || isSearching} onClick={() => setQuery(q)} className="px-2.5 py-1 rounded-full border border-border bg-white/60 hover:bg-white transition">
                {q}
              </button>
            ))}
          </div>
        </form>
      </section>

      {searchStage === "verify_intent" && classification && (
        <section className="mt-2 animate-in fade-in slide-in-from-bottom-4 duration-300">
          {initialSummary && (
            <div className="mb-6 soft-card rounded-2xl p-6 border-t-4 border-t-primary relative overflow-hidden bg-white shadow-sm">
               <h3 className="text-sm uppercase tracking-wider text-muted-foreground font-bold mb-3 flex items-center gap-2">
                 <Sparkles className="h-4 w-4 text-primary"/> Initial AI Summary
               </h3>
               <div className="text-[14.5px] leading-relaxed text-foreground/90 font-sans" dangerouslySetInnerHTML={{ __html: formatMainText(initialSummary) }} />
            </div>
          )}

          <div className="grid md:grid-cols-[1.1fr_1fr] gap-5">
            <div className="soft-card rounded-2xl p-6 relative overflow-hidden">
              <div aria-hidden className="absolute -top-24 -right-24 h-64 w-64 rounded-full opacity-40 blur-3xl gradient-primary" />
              <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Step 1: Confirm Intent Routing Strategy</div>
              <div className="mt-3 inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full gradient-primary text-white text-sm font-medium periwinkle-glow">
                💡 Classified Target: {classification.top_intent.toUpperCase()}
              </div>
              <p className="mt-4 text-sm text-muted-foreground max-w-lg">
                Confirm your domain target context below or select an override target taxonomy pathway before initializing live workers.
              </p>
              <div className="mt-4 flex flex-col gap-2 relative z-10">
                <label className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">Target Domain Pathway:</label>
                <select value={chosenIntent} onChange={(e) => setChosenIntent(e.target.value)} className="w-full p-3 rounded-xl border border-border bg-white text-sm outline-none focus:periwinkle-glow">
                  {[classification.top_intent, ...ALL_TAXONOMY_INTENTS.filter(i => i !== classification.top_intent)].map((intent) => (
                    <option key={intent} value={intent}>{INTENT_DISPLAY_NAMES[intent] || intent}</option>
                  ))}
                </select>
              </div>
              <button type="button" onClick={handleConfirmAndScrape} disabled={isSearching} className="mt-6 w-full inline-flex items-center justify-center gap-2 gradient-apricot text-foreground text-sm font-bold py-3.5 rounded-xl periwinkle-glow hover:brightness-105 transition disabled:opacity-50">
                {isSearching ? "Initializing fulfillment tasks..." : "🔥 Confirm & Scrape Sources"}
              </button>
            </div>

            <div className="soft-card rounded-2xl p-6">
              <div className="flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Confidence scores</div>
                <span className="text-[11px] text-muted-foreground font-mono">softmax · v2.4</span>
              </div>
              <div className="mt-4 space-y-3.5">
                {classification.predictions?.slice(0, 4).map((c: any, index: number) => (
                  <ConfidenceBar key={c.label} label={c.label} value={c.score * 100} top={index === 0} />
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {searchStage === "display_results" && results && (
        <section className="mt-8 space-y-5 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className="flex items-center justify-between bg-white border border-border p-4 rounded-xl shadow-sm">
            <div className="flex flex-wrap items-center gap-2 text-[12px]">
              <StatusChip icon={<Timer className="h-3.5 w-3.5" />} label={`${latency}s processing latency`} />
              <StatusChip icon={<Radar className="h-3.5 w-3.5" />} label={`${Object.keys(results.payload || {}).length} platform paths completed`} />
              <StatusChip icon={<Check className="h-3.5 w-3.5" />} label="Execution Pipeline Verified" tone="accent" />
            </div>
            <span className="text-xs font-mono text-muted-foreground">Locked Route: {results.intents_detected?.[0]}</span>
          </div>

          <SectionLabel>Unified fulfillment results canvas</SectionLabel>

          {selectedWikiTitle && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 flex flex-col items-start gap-4 animate-in fade-in zoom-in-95 shadow-sm">
              <div className="flex items-center gap-3">
                <span className="text-2xl">📚</span>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-amber-800">Target Isolation Lock</h4>
                  <p className="text-[14px] text-amber-900 font-medium">Currently targeted context: <strong>{selectedWikiTitle}</strong></p>
                </div>
              </div>
              <div className="bg-white/60 p-4 rounded-lg w-full border border-amber-200/50">
                 {selectedWikiContent ? (
                   <ExpandableHtml htmlContent={formatMainText(selectedWikiContent)} />
                 ) : (
                   <div className="flex items-center gap-3 py-3 text-[14px] text-amber-900">
                     <div className="h-5 w-5 rounded-full border-2 border-amber-300 border-t-amber-700 animate-spin" />
                     Fetching complete Wikipedia article content...
                   </div>
                 )}
              </div>
              <button
                onClick={executeTargetedWikiSynthesis}
                disabled={isReSynthesizingWiki}
                className="gradient-primary text-white text-sm font-bold px-6 py-3 rounded-xl periwinkle-glow hover:brightness-105 disabled:opacity-50 whitespace-nowrap w-full md:w-auto mt-2 transition-all"
              >
                {isReSynthesizingWiki ? "Refactoring context tracking..." : "✨ Re-Synthesize Engine via Selected Article"}
              </button>
            </div>
          )}

          {results.payload?.weather && <WeatherBlock data={results.payload.weather} open={openContracts.weather} onToggle={() => toggle("weather")} />}
          {results.payload?.news && <NewsBlock data={results.payload.news} open={openContracts.news} onToggle={() => toggle("news")} />}
          
          {results.payload?.wikipedia && (
            <WikiBlock 
              data={results.payload.wikipedia} 
              open={openContracts.wikipedia} 
              onToggle={() => toggle("wikipedia")} 
              onSelectArticle={(title, articleUrl) => {
                handleSelectWikiArticle(title, articleUrl);
              }}
            />
          )}
          {medicalResearchData && (
            <MedicalResearchBlock
              data={medicalResearchData}
              open={openContracts.medical_research}
              onToggle={() => toggle("medical_research")}
            />
          )}
          {medicineSourceData && (
            <MedicineBlock
              data={medicineData}
              contractData={results?.raw_contract ?? medicineSourceData}
              open={openContracts.medicine}
              onToggle={() => toggle("medicine")}
            />
          )}
          {nutritionData && (
            <NutritionBlock
              data={nutritionData}
              contractData={nutritionSourceData}
              userQuery={query}
              open={openContracts.food_nutrition}
              onToggle={() => toggle("food_nutrition")}
            />
          )}
          
          {results.payload?.reddit && <RedditBlock data={results.payload.reddit} open={openContracts.reddit} onToggle={() => toggle("reddit")} />}
          {results.payload?.stackoverflow && <StackBlock data={results.payload.stackoverflow} open={openContracts.stack} onToggle={() => toggle("stack")} />}
          {results.payload?.oracle && <OracleBlock data={results.payload.oracle} open={openContracts.oracle} onToggle={() => toggle("oracle")} />}
          {results.payload?.academic_research && <AcademicResearchBlock data={results.payload.academic_research} open={openContracts.academic_research} onToggle={() => toggle("academic_research")} />}
          {results.payload?.google_search && <GoogleSearchBlock data={results.payload.google_search} open={openContracts.google_search} onToggle={() => toggle("google_search")} />}

          {isSynthesizing && !results.ai_synthesis && (
             <div className="soft-card rounded-2xl p-6 border-t-4 border-t-primary relative overflow-hidden bg-white animate-pulse mt-8">
               <h3 className="text-lg font-bold flex items-center gap-2 mb-4 text-muted-foreground">
                 <Sparkles className="h-5 w-5 animate-spin text-primary"/> Generating Bounded Gemini Synthesis...
               </h3>
               <div className="h-3 bg-secondary rounded w-3/4 mb-3"></div>
               <div className="h-3 bg-secondary rounded w-full mb-3"></div>
               <div className="h-3 bg-secondary rounded w-1/2"></div>
            </div>
          )}

          {results.ai_synthesis && (
            <div className="soft-card rounded-2xl p-8 border-t-4 border-t-primary relative overflow-hidden bg-white mt-8 shadow-md animate-in fade-in zoom-in-95 duration-500">
              <div aria-hidden className="absolute -top-32 -right-32 h-96 w-96 rounded-full opacity-10 blur-3xl gradient-primary pointer-events-none" />
              <h3 className="text-xl font-bold flex items-center gap-2 mb-6">
                <Sparkles className="h-6 w-6 text-primary"/> InfoByte Gemini Synthesis Layer
              </h3>
              
              <div className="grid md:grid-cols-2 gap-8 mt-4 relative z-10">
                <div>
                  <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-bold mb-3">Bounded Factual Summary</h4>
                  <div className="text-[14.5px] leading-relaxed text-foreground/90 whitespace-pre-line bg-secondary/10 p-5 rounded-2xl border border-border/50 shadow-inner" dangerouslySetInnerHTML={{ __html: formatMainText(results.ai_synthesis.factual_summary) }} />
                </div>
                <div>
                  <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-bold mb-3">AI Expert Engineering Overview</h4>
                  <div className="text-[14.5px] leading-relaxed text-foreground/90 whitespace-pre-line bg-secondary/10 p-5 rounded-2xl border border-border/50 shadow-inner" dangerouslySetInnerHTML={{ __html: formatMainText(results.ai_synthesis.llm_overview) }} />
                </div>
              </div>
            </div>
          )}

          <button type="button" onClick={() => { setResults(null); setClassification(null); setInitialSummary(null); setSelectedWikiTitle(null); setSelectedWikiContent(null); setSearchStage("input"); }} className="w-full border border-border bg-white py-3 rounded-xl hover:bg-secondary transition font-medium text-sm mt-6">
            🔄 Clear Routing Context Instance
          </button>
        </section>
      )}
    </AppShell>
  );
}

/* ---------- Text Parsers ---------- */

function formatMainText(text: string) {
  if (!text) return "";
  let html = text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary font-semibold hover:underline inline-flex items-center gap-0.5">$1 <svg xmlns="http://www.w3.org/2000/svg" width="11" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg></a>')
    .replace(/(^|\s)(https?:\/\/[^\s]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary font-medium hover:underline break-all">$2</a>')
    .replace(/###\s*(.*)/g, '<h3 class="text-[14.5px] uppercase tracking-wider text-primary font-bold mt-6 mb-2">$1</h3>')
    .replace(/##\s*(.*)/g, '<h2 class="text-[15.5px] font-bold tracking-tight text-foreground mt-6 mb-2">$1</h2>')
    .replace(/#\s*(.*)/g, '<h1 class="text-[17px] font-bold tracking-tight text-foreground mt-6 mb-2">$1</h1>')
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong class="font-bold text-foreground">$1</strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-foreground">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="text-foreground/90">$1</em>')
    .replace(/(?:^|\n)\*\s+(.*)/g, '<li class="ml-4 list-disc mb-1.5 text-foreground/90">$1</li>')
    .replace(/(?:^|\n)-\s+(.*)/g, '<li class="ml-4 list-disc mb-1.5 text-foreground/90">$1</li>')
    .replace(/\n\n/g, '<div class="h-3"></div>')
    .replace(/\n/g, '<br/>');

  return html.replace(/<\/li><br\/>/g, '</li>').replace(/\*\*|\*|###|##/g, ''); 
}

function parseRedditRawText(rawText: string) {
  if (!rawText) return [];
  const threads = [];
  const threadChunks = rawText.split(/(?:===+\s*THREAD|THREAD\s+\d+:)/i).filter(t => t.trim().length > 10);
  
  for (const chunk of threadChunks) {
     const lines = chunk.split('\n');
     const title = lines[0].replace(/===+/g, '').trim();
     
     const bodyMatch = chunk.match(/ORIGINAL POST:\s*([\s\S]*?)(?:TOP COMMENTS:|$)/i);
     const body = bodyMatch ? bodyMatch[1].trim() : "";
     
     const commentsMatch = chunk.match(/TOP COMMENTS:\s*([\s\S]*)$/i);
     const commentsRaw = commentsMatch ? commentsMatch[1].trim() : "";
     
     const comments = [];
     if (commentsRaw) {
         const commentLines = commentsRaw.split(/\n(?=\d+\.\s*\()/);
         for (const line of commentLines) {
             const cleanLine = line.replace(/^\d+\.\s*/, ''); 
             const cMatch = cleanLine.match(/^\((.*?)\):\s*([\s\S]*)/);
             if (cMatch) {
                 comments.push({ author: cMatch[1], text: cMatch[2] });
             } else if (cleanLine.trim().length > 0) {
                 comments.push({ author: "user", text: cleanLine });
             }
         }
     }
     threads.push({ title: title || "Reddit Discussion", body, comments });
  }
  return threads;
}

/* ---------- Shared UI Elements ---------- */

function ExpandableHtml({ htmlContent }: { htmlContent: string }) {
  const [expanded, setExpanded] = useState(false);
  const needsExpansion = htmlContent.length > 400;

  return (
    <div className="relative">
      <div 
         className={`text-[14.5px] leading-relaxed text-foreground/90 font-sans tracking-wide ${needsExpansion && !expanded ? "line-clamp-6 max-h-[170px] overflow-hidden" : ""}`} 
         dangerouslySetInnerHTML={{ __html: htmlContent }} 
      />
      {needsExpansion && !expanded && (
         <div className="absolute bottom-0 left-0 w-full h-20 bg-gradient-to-t from-gray-50/50 via-white/90 to-transparent pointer-events-none" />
      )}
      {needsExpansion && (
         <button 
           onClick={() => setExpanded(!expanded)} 
           className="mt-5 w-full flex items-center justify-center gap-2 bg-primary text-white font-bold py-3.5 rounded-xl transition-all uppercase tracking-widest text-[13px] shadow-md hover:bg-primary/90"
         >
           {expanded ? "Collapse Content" : "Read Full Context"}
           <ChevronDown className={`h-5 w-5 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`} />
         </button>
      )}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{children}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

function StatusChip({ icon, label, tone = "default" }: { icon: React.ReactNode; label: string; tone?: "default" | "accent" }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[12px] ${tone === "accent" ? "bg-[color-mix(in_oklab,var(--apricot)_45%,white)] border-[color-mix(in_oklab,var(--apricot-deep)_45%,transparent)] text-foreground" : "bg-white border-border text-muted-foreground"}`}>
      {icon} {label}
    </span>
  );
}

function ConfidenceBar({ label, value, top }: { label: string; value: number; top?: boolean }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px]">
        <span className="font-mono text-foreground/80">{label}</span>
        <span className={`font-mono ${top ? "text-primary font-semibold" : "text-muted-foreground"}`}>{value.toFixed(1)}%</span>
      </div>
      <div className="mt-1.5 h-1.5 w-full rounded-full bg-secondary overflow-hidden">
        <div className={`h-full rounded-full ${top ? "gradient-primary" : "bg-foreground/20"}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function ResultCard({ icon, title, source, sourceUrl, tone = "periwinkle", children, contract, open, onToggle }: { icon: React.ReactNode; title: string; source: string; sourceUrl?: string; tone?: "periwinkle" | "apricot"; children: React.ReactNode; contract: object; open?: boolean; onToggle: () => void }) {
  return (
    <article className="soft-card rounded-2xl overflow-hidden bg-white border border-border shadow-sm">
      <header className="flex items-center gap-3 px-5 py-4 border-b border-border/70">
        <div className={`h-9 w-9 rounded-xl flex items-center justify-center text-white ${tone === "apricot" ? "gradient-apricot text-foreground" : "gradient-primary"}`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-semibold tracking-tight truncate">{title}</div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{source}</div>
        </div>
        <span className="hidden sm:inline text-[11px] font-mono text-muted-foreground">200 OK</span>
      </header>
      <div className="px-5 py-5">{children}</div>
      <footer className="border-t border-border/70 bg-[color-mix(in_oklab,var(--ivory)_60%,white)]">
        <div className="flex flex-col sm:flex-row sm:items-center">
          <button onClick={onToggle} className="flex-1 flex items-center justify-between px-5 py-2.5 text-[12px] text-muted-foreground hover:text-foreground transition border-b sm:border-b-0 sm:border-r border-border/70">
            <span className="inline-flex items-center gap-2 font-mono"><Code2 className="h-3.5 w-3.5" /> system_data_contract.json</span>
            <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
          {sourceUrl && (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex items-center justify-between sm:justify-end gap-2 px-5 py-2.5 text-[12px] font-bold text-primary hover:brightness-110 transition bg-primary/5 hover:bg-primary/10">
              <span className="sm:hidden">View source</span>
              <span className="hidden sm:inline">🔗 Open Original Source URL</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
        <div className={`grid transition-all duration-300 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
          <div className="overflow-hidden">
            <pre className="text-[12px] leading-relaxed px-5 pb-4 font-mono text-foreground/80 overflow-x-auto border-t border-border bg-gray-50/50">
              <JsonView data={contract} />
            </pre>
          </div>
        </div>
      </footer>
    </article>
  );
}

function JsonView({ data }: { data: unknown }) {
  const str = JSON.stringify(data, null, 2);
  const highlighted = str
    .replace(/(&|<|>)/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] as string))
    .replace(/"([^"\\]*)":/g, '<span style="color:var(--periwinkle-deep)">"$1"</span>:')
    .replace(/: "([^"\\]*)"/g, ': <span style="color:var(--apricot-deep)">"$1"</span>')
    .replace(/: (true|false|null)/g, ': <span style="color:#a855f7">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span style="color:#059669">$1</span>');
  return <code dangerouslySetInnerHTML={{ __html: highlighted }} />;
}

/* ---------- Custom Implementation Blocks ---------- */

function WeatherBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<Cloud className="h-5 w-5" />} title="Weather Extraction Failed" source="OpenWeather Gateway" tone="apricot" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  const mainText = payload.main_text || "";
  const parsedCondition = mainText.split("\n")[0] || "Live Data Feed";

  return (
    <ResultCard icon={<Cloud className="h-5 w-5" />} title={payload.title || "Weather Information Context"} source={payload.metadata?.provider || "OpenWeather API Gateway"} sourceUrl={payload.source_url} tone="apricot" open={open} onToggle={onToggle} contract={data}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricTile label="Condition" value={parsedCondition} sub="Synchronized Real-Time" icon={<Cloud className="h-4 w-4" />} />
        <MetricTile label="Temperature Metrics" value={<div className="flex flex-col leading-tight"><span>{mainText.match(/(-?\d+\.?\d*)\s*°C/)?.[0] || "Data Active"}</span><span className="text-[11px] font-mono text-muted-foreground">{mainText.match(/(-?\d+\.?\d*)\s*K/)?.[0] || "Continuous Feed"}</span></div>} icon={<Thermometer className="h-4 w-4" />} tone="accent" />
        <MetricTile label="Atmospheric Moisture" value={mainText.match(/Humidity:\s*(\d+)%/)?.[1] ? `${mainText.match(/Humidity:\s*(\d+)%/)?.[1]}%` : "Verified Inline"} sub="Barometric Track" icon={<Droplets className="h-4 w-4" />} />
        <MetricTile label="Wind Velocity" value={mainText.match(/Wind:\s*(-?\d+\.?\d*)\s*m\/s/)?.[1] ? `${mainText.match(/Wind:\s*(-?\d+\.?\d*)\s*m\/s/)?.[1]} m/s` : "Calm Drift"} sub="Anemometer State" icon={<Wind className="h-4 w-4" />} />
      </div>
    </ResultCard>
  );
}

function NewsBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<Newspaper className="h-5 w-5" />} title="News Extraction Failed" source="Scraper Service" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  return (
    <ResultCard icon={<Newspaper className="h-5 w-5" />} title={payload.title || "News Retrieval Story Canvas"} source={payload.metadata?.provider || "Scraper Service Wire"} sourceUrl={payload.source_url} open={open} onToggle={onToggle} contract={data}>
      <div className="bg-gray-50/50 p-5 rounded-2xl border shadow-sm">
         <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
      </div>
    </ResultCard>
  );
}

function WikiBlock({ data, open, onToggle, onSelectArticle }: { data: any; open?: boolean; onToggle: () => void, onSelectArticle: (title: string, text: string) => void }) {
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<BookOpen className="h-5 w-5" />} title="Wikipedia Extraction Failed" source="Wikipedia Engine API" tone="apricot" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  const metadata = payload.metadata || {};
  return (
    <ResultCard icon={<BookOpen className="h-5 w-5" />} title={payload.title || "Encyclopedia Search Context"} source="Wikipedia Engine API" sourceUrl={payload.source_url} tone="apricot" open={open} onToggle={onToggle} contract={data}>
      <div className="mb-4 bg-gray-50/50 p-5 rounded-2xl border shadow-sm">
        <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
      </div>
      
      <button 
        onClick={() => onSelectArticle(payload.title || "Primary Subject", payload.source_url || "")}
        className="mb-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-amber-100 border border-amber-300 text-amber-900 font-bold hover:bg-amber-200 transition-colors shadow-sm"
      >
        📌 Isolate This Article for Targeted Summary
      </button>

      {metadata.options && metadata.options.length > 0 && (
        <div className="mt-4 grid sm:grid-cols-2 gap-2">
          {metadata.options.map((opt: any) => (
            <button
              key={opt.url}
              onClick={() => onSelectArticle(opt.title || "Related Subject", opt.url || "")}
              className="flex items-center justify-between text-left rounded-lg border border-border bg-white px-3 py-2 text-[13px] hover:bg-secondary transition w-full"
            >
              <span className="truncate font-medium text-primary">{opt.title || "Related Subject"}</span>
              <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
          ))}
        </div>
      )}
    </ResultCard>
  );
}

function RedditBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<MessageSquare className="h-5 w-5" />} title="Reddit Extraction Failed" source="Community Scraper" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  const metadata = payload.metadata || {};
  let threads = metadata.threads || [];
  if (threads.length === 0 && payload.main_text) {
     threads = parseRedditRawText(payload.main_text);
  }

  return (
    <ResultCard icon={<MessageSquare className="h-5 w-5" />} title={payload.title || "Social Sentiment Analysis Cluster"} source="r/all Community Scraping Engine" sourceUrl={payload.source_url} open={open} onToggle={onToggle} contract={data}>
      {threads.length === 0 && (
        <div className="bg-gray-50/50 p-5 rounded-2xl border shadow-sm">
          <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
        </div>
      )}

      {threads.map((thread: any, idx: number) => (
        <div key={idx} className="mb-4 border border-border rounded-2xl p-5 bg-white shadow-sm">
          <div className="flex items-center justify-between mb-3 pb-3 border-b border-border/60">
            <h4 className="text-[14px] font-semibold text-primary truncate max-w-[80%] flex items-center gap-2">
              <span className="text-xl">🔥</span> {thread.title}
            </h4>
            {thread.score && <span className="text-xs font-mono text-muted-foreground bg-secondary px-2 py-1 rounded-md">Score: {thread.score}</span>}
          </div>
          
          {thread.body && (
            <div className="mb-4 bg-secondary/10 p-4 border border-border/50 rounded-xl">
               <ExpandableHtml htmlContent={formatMainText(thread.body)} />
            </div>
          )}
          
          <div className="space-y-3 pl-4 border-l-2 border-dashed border-primary/30">
            {thread.comments?.map((comment: any, cIdx: number) => (
              <div key={cIdx} className="rounded-xl bg-white border border-border p-3 shadow-sm hover:border-primary/40 transition-colors">
                <div className="flex items-center justify-between text-[11px] text-muted-foreground mb-1.5">
                  <span className="font-mono font-bold text-foreground/80">{comment.author || "u/anonymous"}</span>
                  {comment.score && <span className="inline-flex items-center gap-1"><ArrowUp className="h-3 w-3 text-primary" /> {comment.score}</span>}
                </div>
                <p className="text-[13px] leading-relaxed text-foreground/90">{comment.text}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </ResultCard>
  );
}

function StackBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<Code2 className="h-5 w-5" />} title="StackOverflow Extraction Failed" source="Gateway Fulfillment" tone="apricot" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  const metadata = payload.metadata || {};
  const answers = metadata.answers || [];
  return (
    <ResultCard icon={<Code2 className="h-5 w-5" />} title={payload.title || "Technical Forum Resolution Block"} source="StackOverflow Gateway" sourceUrl={payload.source_url} tone="apricot" open={open} onToggle={onToggle} contract={data}>
      <div className="bg-white p-4 border border-border rounded-xl text-[14.5px] mb-4 shadow-sm">
        <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
      </div>
      {answers.map((answer: any, idx: number) => (
        <div key={idx} className="flex items-start gap-3 border-t border-border/80 pt-4 mt-2">
          <div className="flex flex-col items-center gap-1 min-w-[58px]">
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-50 text-emerald-700 text-[10px] px-1.5 py-0.5 font-bold uppercase">{idx === 0 ? "Top Answer" : "Solution"}</div>
            <div className="text-[12px] font-mono font-semibold text-gray-600">Score: {answer.score || "N/A"}</div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="bg-gray-50/50 p-4 rounded-xl border">
               <ExpandableHtml htmlContent={formatMainText(answer.text)} />
            </div>
            {answer.comments && answer.comments.length > 0 && (
              <div className="mt-3">
                <button type="button" onClick={() => setExpanded(!expanded)} className="inline-flex items-center gap-2 text-[11px] font-medium text-primary hover:underline">
                  {expanded ? "Hide" : "Show"} troubleshooting context comments ({answer.comments.length}) <ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
                </button>
                {expanded && (
                  <div className="mt-2 rounded-xl bg-white border border-border p-3 text-[12.5px] leading-relaxed text-foreground/80 space-y-2 shadow-inner">
                    {answer.comments.map((cmnt: any, cIdx: number) => (
                      <p key={cIdx} className="border-b border-gray-50 pb-2 last:border-0 last:pb-0"><span className="font-mono font-semibold text-primary">{cmnt.author || "expert"}:</span> {cmnt.text}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </ResultCard>
  );
}

function OracleBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<Database className="h-5 w-5" />} title="Oracle Extraction Failed" source="Oracle Gateway Fulfillment" tone="apricot" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  const metadata = payload.metadata || {};
  const replies = metadata.replies || [];

  return (
    <ResultCard icon={<Database className="h-5 w-5" />} title={payload.title || "Oracle Forums Fulfillment"} source="Oracle Gateway Fulfillment" sourceUrl={payload.source_url} tone="apricot" open={open} onToggle={onToggle} contract={data}>
      <div className="bg-white p-4 border border-border rounded-xl text-[14.5px] mb-4 shadow-sm">
        <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
      </div>

      {replies.map((replyText: string, idx: number) => {
        const lines = replyText.split("\n");
        const author = lines[0] || "Oracle Community Member";
        const date = lines.length > 1 ? lines[1] : "Forum Reply";
        const content = lines.slice(2).join("\n") || replyText;

        return (
          <div key={idx} className="flex items-start gap-3 border-t border-border/80 pt-4 mt-2">
            <div className="flex flex-col items-center gap-1 min-w-[64px]">
              <div className="rounded-lg border border-primary/30 bg-primary/10 text-primary text-[10px] px-1.5 py-0.5 font-bold uppercase text-center w-full">
                Reply {idx + 1}
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="bg-gray-50/50 p-4 rounded-xl border">
                 <div className="flex items-center gap-2 mb-2 pb-2 border-b border-border/50 text-[12px] text-muted-foreground">
                    <strong className="text-foreground/80 font-mono">{author}</strong>
                    <span>•</span>
                    <span>{date.replace("— edited", "").replace("on", "").trim()}</span>
                 </div>
                 <ExpandableHtml htmlContent={formatMainText(content)} />
              </div>
            </div>
          </div>
        );
      })}
    </ResultCard>
  );
}

function AcademicResearchBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data?.display_payload || {};
  const metadata = payload?.metadata || data?.metadata || {};

  if (data?.error || payload?.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard
        icon={<BookOpen className="h-5 w-5" />}
        title="Academic Research Retrieval Failed"
        source="Academic Research Engine"
        open={open}
        onToggle={onToggle}
        contract={data}
      >
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">
          {payload?.main_text || data?.error || "Unable to retrieve academic research results."}
        </div>
      </ResultCard>
    );
  }

  const papers = Array.isArray(payload?.results)
    ? payload.results
    : Array.isArray(data?.results)
      ? data.results
      : [];

  const renderAuthors = (authors: any) => {
    if (!authors) return "Authors unavailable";

    if (Array.isArray(authors)) {
      const names = authors
        .map((author: any) =>
          typeof author === "string"
            ? author
            : author?.name || author?.display_name || author?.author_name || ""
        )
        .filter(Boolean);

      return names.length > 0 ? names.join(", ") : "Authors unavailable";
    }

    return String(authors);
  };

  const formatDate = (value: any) => {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <ResultCard
      icon={<BookOpen className="h-5 w-5" />}
      title={payload?.title || "Academic Research"}
      source="arXiv + OpenAlex Research Engine"
      sourceUrl={payload?.source_url}
      open={open}
      onToggle={onToggle}
      contract={data}
    >
      {payload?.main_text && (
        <div className="mb-5 rounded-2xl border border-border bg-secondary/10 px-5 py-4 text-[14px] text-foreground/90 shadow-sm">
          {payload.main_text}
        </div>
      )}

      {papers.length > 0 ? (
        <div className="space-y-5">
          {papers.map((paper: any, idx: number) => {
            const rawSource = String(paper?.source || "academic").toLowerCase();
            const sourceLabel =
              rawSource === "arxiv"
                ? "arXiv"
                : rawSource === "openalex" || rawSource === "open_alex"
                  ? "OpenAlex"
                  : paper?.source || "Academic";

            const title = paper?.title || "Untitled research paper";
            const authors = renderAuthors(paper?.authors);
            const abstract =
              paper?.abstract ||
              paper?.summary ||
              paper?.description ||
              "No abstract was provided by this source.";

            const published = formatDate(
              paper?.published || paper?.publication_date || paper?.publication_year || paper?.year
            );

            const updated = formatDate(paper?.updated);
            const citationCount = paper?.citation_count ?? paper?.cited_by_count ?? null;

            const categories = Array.isArray(paper?.categories)
              ? paper.categories
              : paper?.categories
                ? [paper.categories]
                : paper?.category
                  ? [paper.category]
                  : [];

            const paperUrl = paper?.url || paper?.paper_url || paper?.entry_id || paper?.doi_url || paper?.id;
            const pdfUrl = paper?.pdf_url;

            return (
              <article
                key={`${rawSource}-${paper?.paper_id || paper?.id || paperUrl || title}-${idx}`}
                className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm transition hover:border-primary/40 hover:shadow-md"
              >
                <div className="px-5 py-5 md:px-6">
                  <div className="flex flex-col gap-3 border-b border-border/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-primary">
                          {sourceLabel}
                        </span>

                        {published && (
                          <span className="rounded-md bg-secondary px-2 py-1 text-[11px] font-mono text-muted-foreground">
                            {published}
                          </span>
                        )}

                        {citationCount !== null && (
                          <span className="rounded-md bg-secondary px-2 py-1 text-[11px] font-mono text-muted-foreground">
                            {citationCount} citations
                          </span>
                        )}
                      </div>

                      <h4 className="text-[16px] font-bold leading-snug tracking-tight text-primary md:text-[17px]">
                        {title}
                      </h4>
                    </div>

                    <span className="shrink-0 text-[11px] font-mono text-muted-foreground">
                      Paper {idx + 1}
                    </span>
                  </div>

                  <div className="mt-4">
                    <div className="text-[11px] font-bold uppercase tracking-[0.13em] text-muted-foreground">
                      Authors
                    </div>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/85">
                      {authors}
                    </p>
                  </div>

                  <div className="mt-4 rounded-xl border border-border/60 bg-secondary/10 p-4 md:p-5">
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.13em] text-muted-foreground">
                      Abstract
                    </div>
                    <ExpandableHtml htmlContent={formatMainText(abstract)} />
                  </div>

                  {(categories.length > 0 || updated) && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {categories.map((category: string, categoryIdx: number) => (
                        <span
                          key={`${category}-${categoryIdx}`}
                          className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-mono text-muted-foreground"
                        >
                          {category}
                        </span>
                      ))}

                      {updated && (
                        <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-mono text-muted-foreground">
                          Updated: {updated}
                        </span>
                      )}
                    </div>
                  )}

                  {(paperUrl || pdfUrl) && (
                    <div className="mt-5 flex flex-wrap gap-2 border-t border-border/60 pt-4">
                      {paperUrl && (
                        <a
                          href={paperUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-[12px] font-bold text-white transition hover:brightness-105"
                        >
                          Open Research Paper
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </a>
                      )}

                      {pdfUrl && (
                        <a
                          href={pdfUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-2.5 text-[12px] font-bold text-primary transition hover:bg-primary/10"
                        >
                          Open PDF
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-[14px] text-amber-900">
          The academic retrieval request completed, but no paper records were found in
          <code className="mx-1 rounded bg-white/70 px-1.5 py-0.5 font-mono text-[12px]">
            display_payload.results
          </code>.
        </div>
      )}

      {Array.isArray(metadata?.successful_sources) && metadata.successful_sources.length > 0 && (
        <div className="mt-5 border-t border-border/60 pt-4 text-[11px] font-mono text-muted-foreground">
          Successful sources: {metadata.successful_sources.join(", ")}
        </div>
      )}
    </ResultCard>
  );
}

function MedicalResearchBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data?.display_payload || {};
  const sections = payload?.sections || data?.sections || {};

  const publications = Array.isArray(sections?.europe_pmc?.results)
    ? sections.europe_pmc.results
    : Array.isArray(data?.source_results?.europe_pmc)
    ? data.source_results.europe_pmc
    : [];

  const trials = Array.isArray(sections?.clinical_trials?.results)
    ? sections.clinical_trials.results
    : Array.isArray(data?.source_results?.clinical_trials)
    ? data.source_results.clinical_trials
    : [];

  if (data?.error) {
    return (
      <ResultCard
        icon={<BookOpen className="h-5 w-5" />}
        title="Medical Research Retrieval Failed"
        source="Medical Research Engine"
        tone="apricot"
        open={open}
        onToggle={onToggle}
        contract={data}
      >
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl">
          {data.error}
        </div>
      </ResultCard>
    );
  }

  return (
    <ResultCard
      icon={<BookOpen className="h-5 w-5" />}
      title="Medical Research"
      source="Europe PMC + ClinicalTrials.gov"
      open={open}
      onToggle={onToggle}
      contract={data}
    >
      {publications.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <BookOpen className="h-5 w-5 text-primary" />
            <h4 className="text-[16px] font-bold">Medical Publications</h4>
            <span className="bg-primary/10 text-primary rounded-full px-2.5 py-1 text-[11px] font-bold">
              {publications.length} results
            </span>
          </div>

          <div className="space-y-4">
            {publications.map((paper: any, idx: number) => (
              <article key={paper?.id || paper?.pmid || idx} className="rounded-2xl border border-border bg-white p-5 shadow-sm">
                <div className="flex flex-wrap gap-2 mb-3">
                  <span className="rounded-full bg-primary/10 text-primary px-2.5 py-1 text-[10px] font-bold uppercase">
                    Europe PMC
                  </span>
                  {paper?.publication_date && (
                    <span className="rounded-md bg-secondary px-2 py-1 text-[11px]">
                      {paper.publication_date}
                    </span>
                  )}
                  {paper?.is_open_access && (
                    <span className="rounded-md bg-emerald-50 text-emerald-700 px-2 py-1 text-[11px] font-bold">
                      Open Access
                    </span>
                  )}
                </div>

                <h5 className="text-[16px] font-bold text-primary leading-snug">
                  {paper?.title || "Untitled publication"}
                </h5>

                <p className="mt-2 text-[13px] text-foreground/80">
                  {paper?.authors || "Authors unavailable"}
                </p>

                <div className="mt-4 grid sm:grid-cols-2 gap-2 text-[12px] text-muted-foreground">
                  <div><strong>Journal:</strong> {paper?.journal || "Not available"}</div>
                  <div><strong>Citations:</strong> {paper?.citation_count ?? 0}</div>
                  {paper?.pmid && <div><strong>PMID:</strong> {paper.pmid}</div>}
                  {paper?.doi && <div className="break-all"><strong>DOI:</strong> {paper.doi}</div>}
                </div>

                {paper?.url && (
                  <a href={paper.url} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-2 bg-primary text-white rounded-lg px-4 py-2.5 text-[12px] font-bold">
                    Open Publication <ArrowUpRight className="h-3.5 w-3.5" />
                  </a>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {trials.length > 0 && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <Database className="h-5 w-5 text-primary" />
            <h4 className="text-[16px] font-bold">Clinical Trials</h4>
            <span className="bg-primary/10 text-primary rounded-full px-2.5 py-1 text-[11px] font-bold">
              {trials.length} results
            </span>
          </div>

          <div className="space-y-4">
            {trials.map((trial: any, idx: number) => (
              <article key={trial?.nct_id || idx} className="rounded-2xl border border-border bg-white p-5 shadow-sm">
                <div className="flex flex-wrap gap-2 mb-3">
                  <span className="rounded-full bg-primary/10 text-primary px-2.5 py-1 text-[10px] font-bold uppercase">
                    ClinicalTrials.gov
                  </span>
                  {trial?.status && (
                    <span className="rounded-md bg-secondary px-2 py-1 text-[11px] font-bold">
                      {String(trial.status).replaceAll("_", " ")}
                    </span>
                  )}
                  {trial?.nct_id && (
                    <span className="text-[11px] font-mono text-muted-foreground">{trial.nct_id}</span>
                  )}
                </div>

                <h5 className="text-[16px] font-bold text-primary leading-snug">
                  {trial?.title || "Untitled clinical trial"}
                </h5>

                {trial?.summary && (
                  <div className="mt-4 bg-secondary/10 border border-border/60 rounded-xl p-4">
                    <ExpandableHtml htmlContent={formatMainText(trial.summary)} />
                  </div>
                )}

                <div className="mt-4 grid sm:grid-cols-2 gap-2 text-[12px] text-muted-foreground">
                  <div><strong>Study type:</strong> {trial?.study_type || "Not available"}</div>
                  <div><strong>Sponsor:</strong> {trial?.sponsor || "Not available"}</div>
                  <div><strong>Enrollment:</strong> {trial?.enrollment ?? "Not available"}</div>
                  <div><strong>Phase:</strong> {trial?.phases?.length ? trial.phases.join(", ") : "Not specified"}</div>
                  <div><strong>Start:</strong> {trial?.start_date || "Not available"}</div>
                  <div><strong>Completion:</strong> {trial?.completion_date || "Not available"}</div>
                </div>

                {trial?.conditions?.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {trial.conditions.slice(0, 8).map((condition: string, conditionIdx: number) => (
                      <span key={`${condition}-${conditionIdx}`} className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground">
                        {condition}
                      </span>
                    ))}
                  </div>
                )}

                {trial?.url && (
                  <a href={trial.url} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-2 bg-primary text-white rounded-lg px-4 py-2.5 text-[12px] font-bold">
                    Open Clinical Trial <ArrowUpRight className="h-3.5 w-3.5" />
                  </a>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {publications.length === 0 && trials.length === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-amber-900">
          No Europe PMC publications or clinical trial records were returned.
        </div>
      )}
    </ResultCard>
  );
}

function MedicineBlock({
  data,
  contractData,
  open,
  onToggle
}: {
  data?: any;
  contractData: any;
  open?: boolean;
  onToggle: () => void;
}) {
  const isStructured = !!data?.cards;
  const medInfo = data?.medicine || {};
  const cards = data?.cards || [];
  const sources = data?.sources || [];
  
  // Fallback for combination medicines preserved in the contract data
  const payloadRoot = contractData?.payload || contractData || {};
  const ingredientLabels = payloadRoot.ingredient_labels || [];
  const isCombination = ingredientLabels.length > 1;

  const productName = medInfo.name || medInfo.generic_name || "Medicine Information";
  const manufacturer = medInfo.manufacturer;
  const genericName = medInfo.generic_name;
  const strength = medInfo.strength;
  const route = Array.isArray(medInfo.route) ? medInfo.route.join(", ") : medInfo.route;

  const IconComponent = ({ name }: { name: string }) => {
    const icons: Record<string, any> = { 
      pill: Database, 
      schedule: Timer, 
      activity: Activity, 
      "alert-triangle": AlertTriangle, 
      "x-circle": AlertTriangle, 
      info: Info 
    };
    const Icon = icons[name] || Check;
    return <Icon className="h-5 w-5" />;
  };

  const renderMedicineCard = (card: any, displayTitle: string, idx: number) => {
    return (
      <div key={idx} className={`rounded-2xl border p-5 shadow-sm ${card.type === 'warning' ? 'border-amber-200 bg-amber-50/50' : 'border-border bg-white'}`}>
        <div className={`flex items-center gap-2 mb-4 ${card.type === 'warning' ? 'text-amber-700' : 'text-primary'}`}>
          <IconComponent name={card.icon} />
          <h5 className="text-[14px] font-bold uppercase tracking-wider">{displayTitle}</h5>
        </div>
        
        {card.type === 'list' || card.type === 'warning' ? (
          <ul className="space-y-2 text-[13.5px] leading-relaxed text-foreground/85">
            {card.items?.length > 0 ? card.items.map((item: string, i: number) => (
              <li key={i} className="flex items-start gap-2">
                <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${card.type === 'warning' ? 'bg-amber-500' : 'bg-primary'}`} />
                <span>{item}</span>
              </li>
            )) : <li className="text-muted-foreground italic">No details provided.</li>}
          </ul>
        ) : (
          <div className="text-[13.5px] leading-relaxed text-foreground/85 whitespace-pre-line">
            {card.content || card.items?.join("\n")}
          </div>
        )}
      </div>
    );
  };

  const groupedCombinationCards = useMemo(() => {
    if (!isCombination || !cards.length) return null;
    const groups: Record<string, any[]> = {};
    cards.forEach((card: any) => {
      const parts = card.title.split(" - ");
      if (parts.length > 1) {
        const groupName = parts[0];
        if (!groups[groupName]) groups[groupName] = [];
        groups[groupName].push({ ...card, displayTitle: parts.slice(1).join(" - ") });
      } else {
        const groupName = "General Information";
        if (!groups[groupName]) groups[groupName] = [];
        groups[groupName].push({ ...card, displayTitle: card.title });
      }
    });
    return groups;
  }, [cards, isCombination]);

  if (data?.error || contractData?.error) {
    return (
      <ResultCard
        icon={<Database className="h-5 w-5" />}
        title="Medicine Retrieval Failed"
        source="Medicine Intelligence Engine"
        tone="apricot"
        open={open}
        onToggle={onToggle}
        contract={contractData}
      >
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-[14px] font-medium text-red-800">
          {data?.error || contractData?.error}
        </div>
      </ResultCard>
    );
  }

  return (
    <ResultCard
      icon={<Database className="h-5 w-5" />}
      title={productName}
      source={isCombination ? "Indian Medicine Resolution" : "openFDA + DailyMed Intelligence"}
      sourceUrl={sources[0]?.url}
      tone="apricot"
      open={open}
      onToggle={onToggle}
      contract={contractData}
    >
      <div className="space-y-6">
        {/* Profile Header */}
        <section className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
          <div className="bg-secondary/10 px-5 py-5 md:px-6">
            <div className="flex justify-between items-start">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">Medicine Profile</div>
                <h4 className="mt-1 text-[22px] font-bold tracking-tight text-foreground">{productName}</h4>
                {genericName && (
                  <p className="mt-1 text-[13px] text-muted-foreground">Generic: <span className="font-medium text-foreground/85">{genericName}</span></p>
                )}
              </div>
              {isCombination && (
                <span className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.13em] text-primary">
                  Combination medicine
                </span>
              )}
            </div>
            
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {manufacturer && (
                <div className="rounded-xl border border-border/60 bg-white p-3 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Manufacturer</div>
                  <div className="mt-1 text-[13px] font-medium leading-relaxed text-foreground/85">{manufacturer}</div>
                </div>
              )}
              {strength && (
                <div className="rounded-xl border border-border/60 bg-white p-3 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Strength</div>
                  <div className="mt-1 text-[13px] font-medium leading-relaxed text-foreground/85">{strength}</div>
                </div>
              )}
              {route && (
                <div className="rounded-xl border border-border/60 bg-white p-3 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Route</div>
                  <div className="mt-1 text-[13px] font-medium leading-relaxed text-foreground/85">{route}</div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Combination Warning Box */}
        {isCombination && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 mb-2">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-lg bg-white p-2 shadow-sm">
                <BookOpen className="h-4 w-4 text-amber-700" />
              </div>
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.13em] text-amber-800">
                  Combination label context
                </div>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-amber-950">
                  This is a combination medicine. Clinical information is shown separately for each active ingredient below and should not be interpreted as one official label for the complete combination product.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Structured Frontend Cards */}
        {isStructured && cards.length > 0 ? (
          isCombination && groupedCombinationCards ? (
            <div className="grid gap-6 items-start grid-cols-1 md:grid-cols-2">
              {Object.entries(groupedCombinationCards).map(([groupName, groupCards], groupIdx) => (
                <div key={groupIdx} className="flex flex-col gap-4">
                  <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-center shadow-sm">
                    <h4 className="text-[13px] font-bold uppercase tracking-[0.16em] text-primary">{groupName}</h4>
                  </div>
                  {groupCards.map((card, idx) => renderMedicineCard(card, card.displayTitle, idx))}
                </div>
              ))}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {cards.map((card: any, idx: number) => renderMedicineCard(card, card.title, idx))}
            </div>
          )
        ) : (
          <div className="rounded-2xl border border-border bg-secondary/10 p-5 text-sm text-muted-foreground text-center">
            No structured clinical information available. Check the raw contract data below.
          </div>
        )}
      </div>
    </ResultCard>
  );
}

function NutritionBlock({
  data,
  contractData,
  userQuery = "",
  open,
  onToggle,
}: {
  data: NutritionData;
  contractData: any;
  userQuery?: string;
  open?: boolean;
  onToggle: () => void;
}) {
  const [currentData, setCurrentData] = useState<NutritionData>(data);
  const [isLoadingAlternative, setIsLoadingAlternative] = useState<boolean>(false);
  const [loadingFdcId, setLoadingFdcId] = useState<number | string | null>(null);

  const initialGramValue =
    currentData.requested_portion?.amount || 100;
  const [selectedGrams, setSelectedGrams] = useState<number>(initialGramValue);
  const [customGramInput, setCustomGramInput] = useState<string>(String(initialGramValue));

  const foodName =
    currentData.food_name ||
    currentData.description ||
    "Food & Nutrition Information";
  const foodCategory =
    currentData.food_category ||
    "";
  const dataType =
    currentData.data_type ||
    "";
  const brandOwner =
    currentData.brand_owner ||
    null;
  const fdcId = currentData.fdc_id || null;
  const sourceUrl =
    (currentData.source_url as string) ||
    undefined;
  const nutrientBasis =
    ((currentData.nutrient_basis as Record<string, unknown>)?.display as string) ||
    (currentData.nutrient_basis as string) ||
    "per 100 g";

  const nutrientsObject =
    (currentData.nutrients as Record<string, unknown>) || {};

  const scaledNutrientEntries = useMemo(() => {
    const scaleFactor = selectedGrams / 100.0;
    return Object.entries(nutrientsObject).map(([key, item]) => {
      if (!item || typeof item !== "object") {
        return { key, value: null, display: null };
      }
      const rawVal = (item as any).value;
      const unit = (item as any).unit || "";
      if (rawVal === undefined || rawVal === null) {
        return { key, value: null, display: null };
      }
      const scaled = roundNutrientValue(Number(rawVal) * scaleFactor);
      return {
        key,
        value: scaled,
        display: `${scaled} ${unit}`.trim(),
      };
    }).filter((item) => item.display !== null);
  }, [nutrientsObject, selectedGrams]);

  const primaryNutrientKeys = [
    "energy_kcal",
    "protein",
    "carbohydrates",
    "total_fat",
    "fiber",
    "total_sugars",
  ];

  const primaryNutrientMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const item of scaledNutrientEntries) {
      if (primaryNutrientKeys.includes(item.key) && item.display) {
        map[item.key] = item.display;
      }
    }
    return map;
  }, [scaledNutrientEntries]);

  const rawPortions = Array.isArray(currentData.usda_defined_portions)
    ? (currentData.usda_defined_portions as NutritionPortion[])
    : [];

  const portionCards = rawPortions
    .map((portion) => ({
      label: renderUsdaPortionLabel(portion),
      gramWeight: portion.gram_weight,
      raw: portion,
    }))
    .filter((entry) => Boolean(entry.label) && entry.gramWeight != null);

  const alternativeMatches = Array.isArray(currentData.alternative_matches)
    ? (currentData.alternative_matches as Array<Record<string, unknown>>)
    : [];

  const currentMatchId = fdcId ? String(fdcId) : null;

  const handleGramChange = (newGrams: number) => {
    if (isNaN(newGrams) || newGrams <= 0) return;
    const rounded = Math.round(newGrams * 10) / 10;
    setSelectedGrams(rounded);
    setCustomGramInput(String(rounded));
  };

  const handleSelectAlternativeMatch = async (matchFdcId: number | string) => {
    if (String(matchFdcId) === currentMatchId) return;
    
    setIsLoadingAlternative(true);
    setLoadingFdcId(matchFdcId);
    toast.info("Retrieving selected USDA FoodData Central record...");

    try {
      const activeQuery = currentData.food_name || userQuery || "food";
      const res = await fetch(`${API_BASE}/retriever/nutrition?q=${encodeURIComponent(activeQuery)}&fdc_id=${matchFdcId}&grams=${selectedGrams}`);
      const responseData = await res.json();

      if (!res.ok || responseData.error || responseData.success === false) {
        throw new Error(responseData.error || "Failed to retrieve alternative food record.");
      }

      const newNutritionPayload = normalizeNutritionPayload(responseData);
      if (newNutritionPayload) {
        setCurrentData(newNutritionPayload);
        toast.success(`Switched to: ${newNutritionPayload.food_name || "Selected Food"}`);
      }
    } catch (err: any) {
      toast.error(`Alternative match lookup failed: ${err.message}`);
    } finally {
      setIsLoadingAlternative(false);
      setLoadingFdcId(null);
    }
  };

  if (currentData.error) {
    return (
      <ResultCard icon={<Salad className="h-5 w-5" />} title="Food & Nutrition Retrieval Failed" source="USDA FoodData Central" tone="apricot" open={open} onToggle={onToggle} contract={contractData || data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">
          {currentData.error}
        </div>
      </ResultCard>
    );
  }

  return (
    <ResultCard icon={<Salad className="h-5 w-5" />} title="Food & Nutrition Information" source="USDA FoodData Central" sourceUrl={sourceUrl} open={open} onToggle={onToggle} contract={contractData}>
      <div className="space-y-6">
        <div className="rounded-2xl border border-border bg-secondary/10 p-5 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h3 className="text-xl font-semibold tracking-tight text-foreground">{foodName}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{brandOwner ? `${foodCategory} · ${brandOwner}` : foodCategory}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {dataType && <span className="rounded-full bg-white/90 border border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">{dataType}</span>}
              {foodCategory && <span className="rounded-full bg-white/90 border border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">{foodCategory}</span>}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
            {brandOwner && <span>{brandOwner}</span>}
            {fdcId && <span>FDC ID {fdcId}</span>}
            <span>Basis: {nutrientBasis}</span>
          </div>
        </div>

        {/* Interactive Portion & Gram Scaling Bar */}
        <div className="rounded-2xl border border-primary/30 bg-primary/5 p-5 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2.5">
              <Scale className="h-5 w-5 text-primary shrink-0" />
              <div>
                <h4 className="text-sm font-bold text-foreground uppercase tracking-wider">Interactive Gram Scaling</h4>
                <p className="text-xs text-muted-foreground">Recalculate nutrients for arbitrary gram quantities</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => handleGramChange(100)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition border ${selectedGrams === 100 ? "bg-primary text-white border-primary" : "bg-white border-border text-foreground hover:bg-secondary"}`}
              >
                100 g Basis
              </button>

              {portionCards.slice(0, 3).map((portion, idx) => (
                <button
                  key={`${portion.label}-${idx}`}
                  type="button"
                  onClick={() => handleGramChange(Number(portion.gramWeight))}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition border ${selectedGrams === portion.gramWeight ? "bg-primary text-white border-primary" : "bg-white border-border text-foreground hover:bg-secondary"}`}
                >
                  {portion.label}
                </button>
              ))}

              <div className="flex items-center gap-1.5 bg-white border border-border rounded-xl px-2.5 py-1 focus-within:ring-2 focus-within:ring-primary/40">
                <input
                  type="number"
                  min="1"
                  max="5000"
                  value={customGramInput}
                  onChange={(e) => {
                    setCustomGramInput(e.target.value);
                    const val = parseFloat(e.target.value);
                    if (!isNaN(val) && val > 0) setSelectedGrams(val);
                  }}
                  className="w-16 text-xs font-bold text-foreground outline-none bg-transparent"
                  placeholder="Grams"
                />
                <span className="text-xs font-bold text-muted-foreground">g</span>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-primary/20 flex items-center justify-between text-xs text-primary font-medium">
            <span>Currently displaying nutrition values scaled for <strong>{selectedGrams} g</strong>:</span>
            {selectedGrams !== 100 && (
              <span className="font-mono text-[11px] bg-primary/10 px-2 py-0.5 rounded-md">
                Scaled by {(selectedGrams / 100).toFixed(2)}x
              </span>
            )}
          </div>
        </div>

        {/* Scaled Primary Nutrients Overview */}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {primaryNutrientKeys.map((key) => {
            const valDisplay = primaryNutrientMap[key];
            return (
              <div key={key} className="rounded-2xl border border-border bg-white p-4 shadow-sm">
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{formatNutritionLabel(key)}</div>
                <div className="mt-2 text-[18px] font-semibold text-foreground">{valDisplay || "N/A"}</div>
              </div>
            );
          })}
        </div>

        {/* Detailed Nutrient Profile */}
        <div className="rounded-2xl border border-border bg-white/80 p-5 shadow-sm">
          <div className="mb-4">
            <h4 className="text-lg font-semibold text-foreground">Detailed Nutrient Profile</h4>
            <p className="text-sm text-muted-foreground">Complete nutrient profile mathematically scaled for {selectedGrams} g.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {scaledNutrientEntries.map((nutrient) => (
              <div key={nutrient.key} className="rounded-2xl border border-border bg-secondary/10 p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{formatNutritionLabel(nutrient.key)}</div>
                <div className="mt-2 text-[15px] font-semibold text-foreground">{nutrient.display}</div>
              </div>
            ))}
          </div>
        </div>

        {/* USDA Defined Portion Cards */}
        {portionCards.length > 0 && (
          <div className="rounded-2xl border border-border bg-white/80 p-5 shadow-sm">
            <div className="mb-4">
              <h4 className="text-lg font-semibold text-foreground">USDA Serving Portions</h4>
              <p className="text-sm text-muted-foreground">Click any portion to quickly scale nutrient values.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {portionCards.map((entry, idx) => (
                <button
                  key={`${entry.label}-${idx}`}
                  type="button"
                  onClick={() => handleGramChange(Number(entry.gramWeight))}
                  className={`text-left rounded-2xl border p-4 transition-all ${selectedGrams === entry.gramWeight ? "border-primary bg-primary/10 shadow-sm" : "border-border bg-secondary/10 hover:bg-secondary/20"}`}
                >
                  <div className="text-[14px] font-semibold text-foreground">{entry.label}</div>
                  <div className="mt-1 text-xs text-muted-foreground">Calculates as {entry.gramWeight} grams</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Interactive Alternative USDA Matches */}
        {alternativeMatches.length > 0 && (
          <div className="rounded-2xl border border-border bg-secondary/10 p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h4 className="text-lg font-semibold text-foreground">Interactive Alternative USDA Matches</h4>
                <p className="text-sm text-muted-foreground">Select an alternative match below to dynamically fetch its full nutritional profile.</p>
              </div>
              {isLoadingAlternative && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
            </div>
            <div className="grid gap-3">
              {alternativeMatches.map((match: any, idx: number) => {
                const matchFdcId = match.fdc_id;
                const isSelected = currentMatchId && String(matchFdcId) === currentMatchId;
                const isThisLoading = isLoadingAlternative && String(loadingFdcId) === String(matchFdcId);

                return (
                  <div
                    key={`${matchFdcId || idx}`}
                    onClick={() => handleSelectAlternativeMatch(matchFdcId)}
                    className={`rounded-2xl border p-4 transition-all cursor-pointer ${isSelected ? "border-primary bg-primary/10 shadow-sm" : "border-border bg-white hover:border-primary/50 hover:shadow-md"}`}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="text-[14px] font-semibold text-foreground flex items-center gap-2">
                          {match.description || match.food_name || "Alternative match"}
                          {isThisLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />}
                        </div>
                        <div className="mt-1 text-[12px] text-muted-foreground">{match.data_type || match.type || "USDA match"}</div>
                      </div>
                      {isSelected ? (
                        <span className="rounded-full bg-primary text-white px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] shrink-0">
                          Current Match
                        </span>
                      ) : (
                        <span className="rounded-full border border-primary/30 text-primary hover:bg-primary/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] shrink-0 transition">
                          Select Food
                        </span>
                      )}
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2 text-[12px] text-muted-foreground">
                      {match.food_category && <div>Category: {match.food_category}</div>}
                      {match.brand_owner && <div>Brand: {match.brand_owner}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </ResultCard>
  );
}

function formatNutritionLabel(key: string) {
  const labelMap: Record<string, string> = {
    energy_kcal: "Energy",
    total_fat: "Total Fat",
    total_sugars: "Total Sugars",
    carbohydrates: "Carbohydrates",
    protein: "Protein",
    fiber: "Fiber",
    vitamin_a: "Vitamin A",
    vitamin_d: "Vitamin D",
    vitamin_c: "Vitamin C",
    vitamin_b12: "Vitamin B12",
    monounsaturated_fat: "Monounsaturated Fat",
    polyunsaturated_fat: "Polyunsaturated Fat",
    saturated_fat: "Saturated Fat",
    cholesterol: "Cholesterol",
    sodium: "Sodium",
    potassium: "Potassium",
    calcium: "Calcium",
    iron: "Iron",
    magnesium: "Magnesium",
    phosphorus: "Phosphorus",
    zinc: "Zinc",
    folate: "Folate"
  };
  return labelMap[key] || key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function roundNutrientValue(num: number): number {
  if (num === 0) return 0;
  if (num < 0.1) return Math.round(num * 1000) / 1000;
  if (num < 10) return Math.round(num * 100) / 100;
  return Math.round(num * 10) / 10;
}

function renderUsdaPortionLabel(portion: any) {
  if (!portion || typeof portion !== "object") return null;
  const description = String(portion.description || "").trim();
  const gramWeight = portion.gram_weight != null ? `${portion.gram_weight} g` : null;
  const unit = String(portion.unit || "").trim();
  const modifier = String(portion.modifier || "").trim();
  const hideUnit = !unit || /^undetermined$/i.test(unit);
  const showModifier = modifier && !/^[0-9]+$/.test(modifier);

  const parts = [];
  if (description) parts.push(description);
  if (gramWeight) parts.push(gramWeight);
  else if (!description && portion.amount != null && !hideUnit) {
    parts.push(`${portion.amount} ${unit}`);
  }

  if (showModifier && !description) {
    parts.push(modifier);
  }

  return parts.join(" · ") || null;
}


function GoogleSearchBlock({ data, open, onToggle }: { data: any; open?: boolean; onToggle: () => void }) {
  const payload = data.display_payload || {};
  
  if (data.error || payload.main_text?.includes("Scraper Error")) {
    return (
      <ResultCard icon={<Globe className="h-5 w-5" />} title="Google Search Failed" source="Google Index Automation" open={open} onToggle={onToggle} contract={data}>
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">{payload.main_text || data.error}</div>
      </ResultCard>
    );
  }

  return (
    <ResultCard icon={<Globe className="h-5 w-5" />} title={payload.title || "SERP Organic Crawl Engine"} source="Google Index Automation" sourceUrl={payload.source_url} open={open} onToggle={onToggle} contract={data}>
      <div className="bg-secondary/10 p-5 rounded-2xl border shadow-sm">
         <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
      </div>
    </ResultCard>
  );
}

function MetricTile({ label, value, sub, icon, tone }: { label: string; value: React.ReactNode; sub?: string; icon?: React.ReactNode; tone?: "accent" }) {
  return (
    <div className={`rounded-xl border border-border p-3 ${tone === "accent" ? "bg-[color-mix(in_oklab,var(--apricot)_35%,white)]" : "bg-white"}`}>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{icon}{label}</div>
      <div className="mt-1 text-[15px] font-semibold tracking-tight">{value}</div>
      {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}