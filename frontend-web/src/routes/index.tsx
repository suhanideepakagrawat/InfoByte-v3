import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import {
  Search, Cloud, Newspaper, BookOpen, MessageSquare, Code2, ArrowUpRight,
  ChevronDown, Sparkles, Timer, Radar, Wind, Droplets, Thermometer, ArrowUp, Check, Globe, Database
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

const API_BASE =
  "https://infobyte-v3.onrender.com/api";

const ALL_TAXONOMY_INTENTS = [
  "technical_code", "technical_oracle", "discussion_social",
  "general_wiki", "movies", "weather", "google_search", "academic_research", "medical_research", "medicine"
];

const SCRAPER_MAP: Record<string, string[]> = {
  "technical_oracle": ["oracle", "stackoverflow"],
  "technical_code": ["stackoverflow", "reddit"],
  "general_wiki": ["wiki"],
  "movies": ["wiki"],
  "weather": ["weather"],
  "discussion_social": ["news", "reddit"],
  "google_search": ["google_search"],
  "academic_research": ["academic_research", "google_search"],
  "medical_research": ["medical_research", "google_search"],
  "medicine": ["medicine"]
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

interface MedicineData {
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
  error?: string | null;
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
  
  // States to manage Wiki isolation
  const [selectedWikiTitle, setSelectedWikiTitle] = useState<string | null>(null);
  const [selectedWikiContent, setSelectedWikiContent] = useState<string | null>(null);
  const [isReSynthesizingWiki, setIsReSynthesizingWiki] = useState<boolean>(false);

  const toggle = (k: string) => setOpenContracts((s) => ({ ...s, [k]: !s[k] }));

  const medicalResearchData = results?.payload?.medical_research ?? results?.medical_research;
  const medicineSourceData = results?.payload?.medicine ?? results?.medicine;
  const medicineData: MedicineData | null =
    (medicineSourceData?.payload?.medicine as MedicineData | null) ??
    (medicineSourceData?.medicine as MedicineData | null) ??
    (medicineSourceData?.display_payload?.medicine as MedicineData | null) ??
    (medicineSourceData as MedicineData | null);

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
    
    // 1. Log correction
    fetch(`${API_BASE}/log-correction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, intent: chosenIntent, confidence: String(confidenceScore) }),
    }).catch((err) => console.error("Logging error:", err));

    try {
      // 2. Fetch via router.py to ensure error handling and concurrency are perfect
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
      setIsSearching(false); // Unblock UI immediately to show sources
      
      // 3. Request Gemini Synthesis in background
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
      // Use the existing deployed Wikipedia retriever route.
      // /wikipedia/article does not exist on the current backend and returns 404.
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

      // Do NOT overwrite results.payload.wikipedia here.
      // That object contains the original Wikipedia search/disambiguation card.
      // The selected full article lives only in selectedWikiTitle/selectedWikiContent.
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
      {/* Absolute Middle Loading Overlay Context */}
      {isClassifying && (
        <div className="fixed inset-0 bg-background/60 backdrop-blur-md z-50 flex flex-col items-center justify-center animate-in fade-in duration-200">
          <div className="glass-card rounded-2xl p-8 max-w-sm w-full text-center flex flex-col items-center justify-center gap-4 border border-primary/30 shadow-2xl animate-in zoom-in-95 duration-300">
            <div className="relative h-16 w-16 flex items-center justify-center">
              {/* Animated Outer Periwinkle Spinning Circle Track */}
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
            {["weather in bangalore today", "ethanol fuel in india", "reddit thoughts on rust vs go", "ORA-00001 constraint error"].map((q) => (
              <button key={q} type="button" disabled={isClassifying || isSearching} onClick={() => setQuery(q)} className="px-2.5 py-1 rounded-full border border-border bg-white/60 hover:bg-white transition">
                {q}
              </button>
            ))}
          </div>
        </form>
      </section>

      {/* Step 1: Verify Intent & Initial Summary */}
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
                    <option key={intent} value={intent}>{intent}</option>
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

      {/* Step 2: Display Results */}
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

          {/* Wiki Targeted Render Banner */}
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

          {/* Core Visual Blocks */}
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
              contractData={medicineSourceData}
              open={openContracts.medicine}
              onToggle={() => toggle("medicine")}
            />
          )}
          
          {results.payload?.reddit && <RedditBlock data={results.payload.reddit} open={openContracts.reddit} onToggle={() => toggle("reddit")} />}
          {results.payload?.stackoverflow && <StackBlock data={results.payload.stackoverflow} open={openContracts.stack} onToggle={() => toggle("stack")} />}
          {results.payload?.oracle && <OracleBlock data={results.payload.oracle} open={openContracts.oracle} onToggle={() => toggle("oracle")} />}
          {results.payload?.academic_research && <AcademicResearchBlock data={results.payload.academic_research} open={openContracts.academic_research} onToggle={() => toggle("academic_research")} />}
          {results.payload?.google_search && <GoogleSearchBlock data={results.payload.google_search} open={openContracts.google_search} onToggle={() => toggle("google_search")} />}

          {/* Bounded Gemini Synthesis Layer */}
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

/* ---------- Advanced Markdown & Text Parsers ---------- */

function formatMainText(text: string) {
  if (!text) return "";
  let html = text
    // Replace Markdown Links FIRST so they don't break with other regexes
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary font-semibold hover:underline inline-flex items-center gap-0.5">$1 <svg xmlns="http://www.w3.org/2000/svg" width="11" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg></a>')
    // Catch naked http links
    .replace(/(^|\s)(https?:\/\/[^\s]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary font-medium hover:underline break-all">$2</a>')
    // Replace Headings safely
    .replace(/###\s*(.*)/g, '<h3 class="text-[14.5px] uppercase tracking-wider text-primary font-bold mt-6 mb-2">$1</h3>')
    .replace(/##\s*(.*)/g, '<h2 class="text-[15.5px] font-bold tracking-tight text-foreground mt-6 mb-2">$1</h2>')
    .replace(/#\s*(.*)/g, '<h1 class="text-[17px] font-bold tracking-tight text-foreground mt-6 mb-2">$1</h1>')
    // Replace Bold (handles both *** and **)
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong class="font-bold text-foreground">$1</strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-foreground">$1</strong>')
    // Replace Italic
    .replace(/\*(.*?)\*/g, '<em class="text-foreground/90">$1</em>')
    // Replace Lists
    .replace(/(?:^|\n)\*\s+(.*)/g, '<li class="ml-4 list-disc mb-1.5 text-foreground/90">$1</li>')
    .replace(/(?:^|\n)-\s+(.*)/g, '<li class="ml-4 list-disc mb-1.5 text-foreground/90">$1</li>')
    // Clean rogue orphan structural symbols
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
      {/* Original Question Container */}
      <div className="bg-white p-4 border border-border rounded-xl text-[14.5px] mb-4 shadow-sm">
        <ExpandableHtml htmlContent={formatMainText(payload.main_text)} />
      </div>

      {/* Render the replies parsed directly from the Oracle forum */}
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

  // The academic_research backend returns the unified paper list here:
  // data.display_payload.results
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
            : author?.name ||
              author?.display_name ||
              author?.author_name ||
              ""
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
              paper?.published ||
              paper?.publication_date ||
              paper?.publication_year ||
              paper?.year
            );

            const updated = formatDate(paper?.updated);
            const citationCount =
              paper?.citation_count ?? paper?.cited_by_count ?? null;

            const categories = Array.isArray(paper?.categories)
              ? paper.categories
              : paper?.categories
                ? [paper.categories]
                : paper?.category
                  ? [paper.category]
                  : [];

            const paperUrl =
              paper?.url ||
              paper?.paper_url ||
              paper?.entry_id ||
              paper?.doi_url ||
              paper?.id;

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

      {Array.isArray(metadata?.successful_sources) &&
        metadata.successful_sources.length > 0 && (
          <div className="mt-5 border-t border-border/60 pt-4 text-[11px] font-mono text-muted-foreground">
            Successful sources: {metadata.successful_sources.join(", ")}
          </div>
        )}
    </ResultCard>
  );
}



function MedicalResearchBlock({
  data,
  open,
  onToggle
}: {
  data: any;
  open?: boolean;
  onToggle: () => void;
}) {
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
      {/* EUROPE PMC */}
      {publications.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <BookOpen className="h-5 w-5 text-primary" />

            <h4 className="text-[16px] font-bold">
              Medical Publications
            </h4>

            <span className="bg-primary/10 text-primary rounded-full px-2.5 py-1 text-[11px] font-bold">
              {publications.length} results
            </span>
          </div>

          <div className="space-y-4">
            {publications.map((paper: any, idx: number) => (
              <article
                key={paper?.id || paper?.pmid || idx}
                className="rounded-2xl border border-border bg-white p-5 shadow-sm"
              >
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

                  <div>
                    <strong>Journal:</strong>{" "}
                    {paper?.journal || "Not available"}
                  </div>

                  <div>
                    <strong>Citations:</strong>{" "}
                    {paper?.citation_count ?? 0}
                  </div>

                  {paper?.pmid && (
                    <div>
                      <strong>PMID:</strong> {paper.pmid}
                    </div>
                  )}

                  {paper?.doi && (
                    <div className="break-all">
                      <strong>DOI:</strong> {paper.doi}
                    </div>
                  )}

                </div>

                {paper?.url && (
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex items-center gap-2 bg-primary text-white rounded-lg px-4 py-2.5 text-[12px] font-bold"
                  >
                    Open Publication
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </a>
                )}

              </article>
            ))}
          </div>
        </div>
      )}

      {/* CLINICAL TRIALS */}
      {trials.length > 0 && (
        <div>

          <div className="flex items-center gap-3 mb-4">
            <Database className="h-5 w-5 text-primary" />

            <h4 className="text-[16px] font-bold">
              Clinical Trials
            </h4>

            <span className="bg-primary/10 text-primary rounded-full px-2.5 py-1 text-[11px] font-bold">
              {trials.length} results
            </span>
          </div>

          <div className="space-y-4">

            {trials.map((trial: any, idx: number) => (
              <article
                key={trial?.nct_id || idx}
                className="rounded-2xl border border-border bg-white p-5 shadow-sm"
              >

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
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {trial.nct_id}
                    </span>
                  )}

                </div>

                <h5 className="text-[16px] font-bold text-primary leading-snug">
                  {trial?.title || "Untitled clinical trial"}
                </h5>

                {trial?.summary && (
                  <div className="mt-4 bg-secondary/10 border border-border/60 rounded-xl p-4">
                    <ExpandableHtml
                      htmlContent={formatMainText(trial.summary)}
                    />
                  </div>
                )}

                <div className="mt-4 grid sm:grid-cols-2 gap-2 text-[12px] text-muted-foreground">

                  <div>
                    <strong>Study type:</strong>{" "}
                    {trial?.study_type || "Not available"}
                  </div>

                  <div>
                    <strong>Sponsor:</strong>{" "}
                    {trial?.sponsor || "Not available"}
                  </div>

                  <div>
                    <strong>Enrollment:</strong>{" "}
                    {trial?.enrollment ?? "Not available"}
                  </div>

                  <div>
                    <strong>Phase:</strong>{" "}
                    {trial?.phases?.length
                      ? trial.phases.join(", ")
                      : "Not specified"}
                  </div>

                  <div>
                    <strong>Start:</strong>{" "}
                    {trial?.start_date || "Not available"}
                  </div>

                  <div>
                    <strong>Completion:</strong>{" "}
                    {trial?.completion_date || "Not available"}
                  </div>

                </div>

                {trial?.conditions?.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">

                    {trial.conditions
                      .slice(0, 8)
                      .map(
                        (
                          condition: string,
                          conditionIdx: number
                        ) => (
                          <span
                            key={`${condition}-${conditionIdx}`}
                            className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground"
                          >
                            {condition}
                          </span>
                        )
                      )}

                  </div>
                )}

                {trial?.url && (
                  <a
                    href={trial.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex items-center gap-2 bg-primary text-white rounded-lg px-4 py-2.5 text-[12px] font-bold"
                  >
                    Open Clinical Trial
                    <ArrowUpRight className="h-3.5 w-3.5" />
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
  data?: MedicineData | null;
  contractData: any;
  open?: boolean;
  onToggle: () => void;
}) {
  const medicine = data && typeof data === "object" ? data : {};
  const brandName = getDisplayMedicineText(medicine?.brand_name);
  const genericName = getDisplayMedicineText(medicine?.generic_name);
  const name = getDisplayMedicineText(medicine?.name);
  const manufacturer = getDisplayMedicineText(medicine?.manufacturer);
  const route = getDisplayMedicineText(getMedicineRouteValue(medicine?.route));
  const activeIngredients = getDisplayMedicineText(getMedicineActiveIngredients(medicine?.active_ingredients));
  const uses = getDisplayMedicineText(medicine?.uses);
  const dosage = medicine?.dosage || {};
  const structuredDosageRows = [
    { label: "Amount per dose", value: getDisplayMedicineText(dosage?.amount_per_dose) },
    { label: "Frequency", value: getDisplayMedicineText(dosage?.frequency) },
    { label: "Maximum dose", value: getDisplayMedicineText(dosage?.maximum_dose) },
  ].filter((row) => row.value);
  const labelInstructions = getDisplayMedicineText(dosage?.label_instructions);
  const sideEffects = getDisplayMedicineText(medicine?.side_effects);
  const warnings = getDisplayMedicineText(medicine?.warnings);
  const precautions = getDisplayMedicineText(medicine?.precautions);
  const officialLabelUrl = getDisplayMedicineText(medicine?.official_label_url) || getDisplayMedicineText(contractData?.official_label_url);
  const title = brandName || name || genericName || "Medicine Information";
  const ingredientSections = getMedicineIngredientSections(medicine);

  if (medicine?.error || contractData?.error) {
    return (
      <ResultCard
        icon={<BookOpen className="h-5 w-5" />}
        title="Medicine Retrieval Failed"
        source="openFDA + DailyMed"
        tone="apricot"
        open={open}
        onToggle={onToggle}
        contract={contractData || medicine}
      >
        <div className="bg-red-50 text-red-800 p-4 border border-red-200 rounded-xl text-[14px] font-medium">
          {medicine?.error || contractData?.error || "Unable to retrieve medicine information."}
        </div>
      </ResultCard>
    );
  }

  return (
    <ResultCard
      icon={<BookOpen className="h-5 w-5" />}
      title={title}
      source="openFDA + DailyMed"
      sourceUrl={officialLabelUrl || undefined}
      open={open}
      onToggle={onToggle}
      contract={contractData || medicine}
    >
      <div className="space-y-5">
        <div className="rounded-2xl border border-border bg-secondary/10 p-5 shadow-sm">
          <div className="grid gap-3 sm:grid-cols-2">
            {brandName && renderMedicineSummaryItem("Brand Name", brandName)}
            {genericName && renderMedicineSummaryItem("Generic Name", genericName)}
            {activeIngredients && renderMedicineSummaryItem("Active Ingredients", activeIngredients)}
            {manufacturer && renderMedicineSummaryItem("Manufacturer", manufacturer)}
            {route && renderMedicineSummaryItem("Route", route)}
          </div>
        </div>

        {uses && (
          <MedicineAccordionSection title="Uses">
            <MedicineLabelSection rawText={uses} kind="uses" />
          </MedicineAccordionSection>
        )}

        {(structuredDosageRows.length > 0 || labelInstructions) && (
          <MedicineAccordionSection title="Dosage & Administration">
            {structuredDosageRows.length > 0 && (
              <div className="mb-4 rounded-xl border border-border bg-white/80 p-4 shadow-sm">
                <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Structured Summary</div>
                <div className="mt-3 space-y-2 text-[13px] text-foreground/85">
                  {structuredDosageRows.map((row) => (
                    <div key={row.label} className="flex flex-col gap-1 border-b border-border/60 pb-2 last:border-0 last:pb-0 sm:flex-row sm:justify-between">
                      <span className="font-semibold text-foreground/90">{row.label}</span>
                      <span className="text-muted-foreground">{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {labelInstructions && (
              <div className="rounded-xl border border-border bg-secondary/10 p-4 shadow-sm">
                <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Official label instructions</div>
                <MedicineLabelSection rawText={labelInstructions} kind="dosage" />
              </div>
            )}
          </MedicineAccordionSection>
        )}

        {sideEffects && (
          <MedicineAccordionSection title="Side Effects">
            <MedicineLabelSection rawText={sideEffects} kind="sideEffects" />
          </MedicineAccordionSection>
        )}

        {warnings && (
          <MedicineAccordionSection title="Warnings">
            <MedicineLabelSection rawText={warnings} kind="warnings" />
          </MedicineAccordionSection>
        )}

        {precautions && (
          <MedicineAccordionSection title="Precautions">
            <MedicineLabelSection rawText={precautions} kind="precautions" />
          </MedicineAccordionSection>
        )}

        {(ingredientSections.active.length > 0 || ingredientSections.inactive.length > 0) && (
          <MedicineAccordionSection title="Ingredients">
            <div className="space-y-4">
              {ingredientSections.active.length > 0 && (
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">ACTIVE INGREDIENTS</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {ingredientSections.active.map((ingredient, ingredientIdx) => (
                      <span
                        key={`${ingredient.name || "ingredient"}-${ingredientIdx}`}
                        className="rounded-full border border-border bg-secondary/20 px-3 py-1.5 text-[12px] font-medium text-foreground/90"
                      >
                        <span>{ingredient.name}</span>
                        {ingredient.strength && <span className="ml-2 text-muted-foreground">— {ingredient.strength}</span>}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {ingredientSections.inactive.length > 0 && (
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">INACTIVE INGREDIENTS</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {ingredientSections.inactive.map((ingredient, ingredientIdx) => (
                      <span
                        key={`${ingredient.name || "ingredient"}-${ingredientIdx}`}
                        className="rounded-full border border-border bg-secondary/20 px-3 py-1.5 text-[12px] font-medium text-foreground/90"
                      >
                        <span>{ingredient.name}</span>
                        {ingredient.strength && <span className="ml-2 text-muted-foreground">— {ingredient.strength}</span>}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </MedicineAccordionSection>
        )}

        {officialLabelUrl && (
          <a
            href={officialLabelUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-[12px] font-bold text-white transition hover:brightness-105"
          >
            Open Official DailyMed Label
            <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </ResultCard>
  );
}

function MedicineAccordionSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-[14px] font-semibold tracking-tight text-foreground">{title}</span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="border-t border-border/70 px-4 py-4">{children}</div>}
    </div>
  );
}

function MedicineLabelSection({ rawText, kind }: { rawText: string; kind: "uses" | "dosage" | "sideEffects" | "warnings" | "precautions" }) {
  const [view, setView] = useState<"formatted" | "raw">("formatted");
  const formattedContent = useMemo(() => renderFormattedMedicineText(rawText, kind), [rawText, kind]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end">
        <MedicineViewToggle value={view} onChange={setView} />
      </div>
      {view === "formatted" ? (
        formattedContent || (
          <div className="rounded-xl border border-border bg-secondary/10 p-4 text-[13px] leading-6 text-foreground/85 whitespace-pre-wrap">
            {rawText}
          </div>
        )
      ) : (
        <div className="rounded-xl border border-border bg-secondary/10 p-4 text-[13px] leading-6 text-foreground/85 whitespace-pre-wrap">
          {rawText}
        </div>
      )}
    </div>
  );
}

function MedicineViewToggle({ value, onChange }: { value: "formatted" | "raw"; onChange: (next: "formatted" | "raw") => void }) {
  return (
    <div className="inline-flex rounded-full border border-border bg-white p-1 shadow-sm">
      <button
        type="button"
        onClick={() => onChange("formatted")}
        className={`rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition ${value === "formatted" ? "bg-primary text-white" : "text-muted-foreground"}`}
      >
        Formatted View
      </button>
      <button
        type="button"
        onClick={() => onChange("raw")}
        className={`rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition ${value === "raw" ? "bg-primary text-white" : "text-muted-foreground"}`}
      >
        Original Label
      </button>
    </div>
  );
}

function renderFormattedMedicineText(rawText: string, kind: "uses" | "dosage" | "sideEffects" | "warnings" | "precautions") {
  const text = (rawText || "").trim();
  if (!text) return null;

  const blocks = splitMedicineSections(text);
  if (blocks.length > 1) {
    return (
      <div className="space-y-3">
        {blocks.map((block, blockIndex) => (
          <LabelSubsection key={`${block.title || "section"}-${blockIndex}`} title={block.title}>
            {renderMedicineBlockContent(block.content, kind)}
          </LabelSubsection>
        ))}
      </div>
    );
  }

  return renderMedicineBlockContent(text, kind);
}

function splitMedicineSections(text: string) {
  const lines = text.split(/\r?\n/).map((line) => line.trimEnd());
  const sections: Array<{ title: string; content: string[] }> = [];

  let current: { title: string; content: string[] } | null = null;

  const flush = () => {
    if (!current) return;
    const content = current.content.filter((line) => line.trim()).join("\n").trim();
    if (content || current.title) {
      sections.push({ title: current.title, content: content ? [content] : [] });
    }
  };

  lines.forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      if (current) {
        current.content.push("");
      }
      return;
    }

    if (isMedicineHeading(line)) {
      flush();
      current = { title: cleanMedicineHeading(line), content: [] };
      return;
    }

    if (!current) {
      current = { title: "", content: [] };
    }
    current.content.push(line);
  });

  flush();

  return sections.filter((section) => section.title || section.content.length > 0);
}

function isMedicineHeading(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (/^\d+(?:\.\d+)*\s+/.test(trimmed)) return true;
  if (/^(adult|pediatric|limitations of use|usage|indications and usage|dosage and administration|adverse reactions|warnings and precautions|clinical trials experience|postmarketing experience|laboratory abnormalities|hepatotoxicity|severe allergic reactions|qt prolongation|precautions)$/i.test(trimmed)) return true;
  if (/^[A-Z][A-Z0-9 /&(),.-]+$/.test(trimmed) && trimmed.split(/\s+/).length <= 8) return true;
  return false;
}

function cleanMedicineHeading(line: string) {
  return line
    .trim()
    .replace(/^\d+(?:\.\d+)*\s+/, "")
    .replace(/\s+/g, " ");
}

function renderMedicineBlockContent(content: string | string[], kind: "uses" | "dosage" | "sideEffects" | "warnings" | "precautions") {
  const normalized = (Array.isArray(content) ? content.join("\n") : content)
    .replace(/\r/g, "")
    .trim();
  if (!normalized) return null;

  const bulletItems = normalized
    .split(/\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("•") || line.startsWith("-"))
    .map((line) => line.replace(/^[-•]\s*/, "").trim())
    .filter(Boolean);

  if (bulletItems.length > 0) {
    return <LabelBulletList items={bulletItems} />;
  }

  const categoryMatches = normalized
    .split(/\n/)
    .map((line) => line.trim())
    .filter((line) => /.+:\s/.test(line) && line.split(":")[0].trim().length > 1);

  if (categoryMatches.length > 0 && kind !== "dosage") {
    return (
      <div className="space-y-2">
        {categoryMatches.map((line, index) => {
          const [category, ...rest] = line.split(":");
          return <LabelCategoryRow key={`${category}-${index}`} category={category.trim()} content={rest.join(":").trim()} />;
        })}
      </div>
    );
  }

  if (kind === "dosage") {
    return renderDosageContent(normalized);
  }

  const paragraphs = normalized
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  if (paragraphs.length > 1) {
    return (
      <div className="space-y-3">
        {paragraphs.map((paragraph, index) => (
          <div key={`${paragraph.slice(0, 20)}-${index}`} className="text-[13px] leading-6 text-foreground/85">
            {paragraph}
          </div>
        ))}
      </div>
    );
  }

  return <div className="text-[13px] leading-6 text-foreground/85 whitespace-pre-wrap">{normalized}</div>;
}

function renderDosageContent(content: string) {
  const lines = content
    .split(/\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const blocks: Array<{ title: string; body: string[] }> = [];
  let current: { title: string; body: string[] } | null = null;

  lines.forEach((line) => {
    const isConditionLike = !/^(recommended dose|dose|duration|dosage|adult|pediatric|children|infants|patients|therapy|treatment|administration)/i.test(line) && !/^[0-9]+/.test(line);
    if (isConditionLike && !line.includes(":") && line.length < 120) {
      if (current) {
        blocks.push(current);
      }
      current = { title: line, body: [] };
      return;
    }

    if (current) {
      current.body.push(line);
    } else {
      blocks.push({ title: "Dosage Information", body: [line] });
    }
  });

  if (current) {
    blocks.push(current);
  }

  if (blocks.length === 0) {
    return <div className="text-[13px] leading-6 text-foreground/85 whitespace-pre-wrap">{content}</div>;
  }

  return (
    <div className="space-y-3">
      {blocks.map((block, index) => (
        <div key={`${block.title}-${index}`} className="rounded-xl border border-border bg-white/70 p-4 shadow-sm">
          <div className="text-[12px] font-bold uppercase tracking-[0.14em] text-primary">{block.title}</div>
          <div className="mt-2 space-y-2 text-[13px] leading-6 text-foreground/85">
            {block.body.length > 0 ? block.body.map((entry, entryIndex) => (
              <div key={`${entry}-${entryIndex}`} className="rounded-lg border border-border/70 bg-secondary/10 px-3 py-2">
                {entry}
              </div>
            )) : <div className="text-muted-foreground">No additional dosage details provided.</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

function LabelSubsection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-white/80 p-4 shadow-sm">
      {title && <div className="mb-3 text-[12px] font-bold uppercase tracking-[0.14em] text-primary">{title}</div>}
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function LabelBulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2 pl-5 text-[13px] leading-6 text-foreground/85">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="list-disc">
          {item}
        </li>
      ))}
    </ul>
  );
}

function LabelCategoryRow({ category, content }: { category: string; content: string }) {
  return (
    <div className="rounded-xl border border-border bg-secondary/10 p-3">
      <div className="text-[12px] font-bold uppercase tracking-[0.14em] text-primary">{category}</div>
      <div className="mt-1 text-[13px] leading-6 text-foreground/85">{content}</div>
    </div>
  );
}

function getDisplayMedicineText(value: any): string | null {
  if (value === null || value === undefined) return null;

  if (typeof value === "string") {
    const text = value.trim();
    return text && text !== "null" && text !== "undefined" ? text : null;
  }

  if (Array.isArray(value)) {
    const parts = value
      .map((item) => getDisplayMedicineText(item))
      .filter(Boolean) as string[];
    return parts.length > 0 ? parts.join("\n") : null;
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, any>)
      .map(([key, nestedValue]) => {
        const text = getDisplayMedicineText(nestedValue);
        return text ? `${key}: ${text}` : null;
      })
      .filter(Boolean) as string[];

    return entries.length > 0 ? entries.join("\n") : null;
  }

  const text = String(value).trim();
  return text && text !== "null" && text !== "undefined" ? text : null;
}

function getMedicineRouteValue(value: any): string | null {
  if (Array.isArray(value)) {
    const parts = value
      .map((item) => getDisplayMedicineText(item))
      .filter(Boolean) as string[];
    return parts.length > 0 ? parts.join(", ") : null;
  }

  return getDisplayMedicineText(value);
}

function getMedicineActiveIngredients(value: any): string | null {
  if (Array.isArray(value)) {
    const parts = value
      .map((item) => getMedicineIngredientToken(item))
      .filter(Boolean) as string[];
    return parts.length > 0 ? parts.join(", ") : null;
  }

  if (value === null || value === undefined) return null;
  return getMedicineIngredientToken(value);
}

function getMedicineIngredientToken(value: any): string | null {
  if (typeof value === "string") {
    const text = value.trim();
    return text && text !== "null" && text !== "undefined" ? text : null;
  }

  if (typeof value === "number") {
    return String(value);
  }

  if (Array.isArray(value)) {
    const parts = value
      .map((item) => getMedicineIngredientToken(item))
      .filter(Boolean) as string[];
    return parts.length > 0 ? parts.join(", ") : null;
  }

  if (value && typeof value === "object") {
    const candidateKeys = [
      "name",
      "ingredient",
      "substance_name",
      "active_ingredient",
      "active_ingredient_name",
      "ingredient_name",
      "substance",
      "strength",
    ];

    const parts = candidateKeys
      .map((key) => getDisplayMedicineText(value[key]))
      .filter(Boolean) as string[];

    if (parts.length > 0) {
      return parts.join(" • ");
    }

    const fallback = getDisplayMedicineText(value);
    return fallback;
  }

  return null;
}

function renderMedicineSummaryItem(label: string, value: string) {
  return (
    <div className="rounded-xl border border-border bg-white px-4 py-3 shadow-sm">
      <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-[14px] font-semibold tracking-tight text-foreground/90">{value}</div>
    </div>
  );
}

function getMedicineIngredientSections(medicine: Record<string, any> | null | undefined) {
  const normalizedIngredients = normalizeMedicineIngredients(medicine?.ingredients);
  const fallbackIngredients = normalizeMedicineIngredientsFromLegacy(medicine?.active_ingredients);

  return {
    active: normalizedIngredients.active.length > 0 ? normalizedIngredients.active : fallbackIngredients.active,
    inactive: normalizedIngredients.inactive.length > 0 ? normalizedIngredients.inactive : fallbackIngredients.inactive,
  };
}

function normalizeMedicineIngredients(ingredients: MedicineIngredients | null | undefined) {
  const active = (ingredients?.active || []).map((ingredient) => normalizeMedicineIngredient(ingredient));
  const inactive = (ingredients?.inactive || []).map((ingredient) => normalizeMedicineIngredient(ingredient));

  return { active, inactive };
}

function normalizeMedicineIngredientsFromLegacy(value: unknown) {
  if (typeof value === "string") {
    return { active: [normalizeMedicineIngredient(value)], inactive: [] };
  }

  if (Array.isArray(value)) {
    return {
      active: value.map((item) => normalizeMedicineIngredient(item)),
      inactive: [],
    };
  }

  if (value && typeof value === "object") {
    return {
      active: [normalizeMedicineIngredient(value)],
      inactive: [],
    };
  }

  return { active: [], inactive: [] };
}

function normalizeMedicineIngredient(value: unknown): MedicineIngredient {
  if (typeof value === "string") {
    return {
      name: getDisplayMedicineText(value),
      strength: null,
    };
  }

  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return {
      name: getDisplayMedicineText(record.name ?? record.ingredient ?? record.ingredient_name ?? record.substance_name),
      strength: getDisplayMedicineText(record.strength ?? record.strength_value ?? record.amount),
    };
  }

  return {
    name: getDisplayMedicineText(value),
    strength: null,
  };
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