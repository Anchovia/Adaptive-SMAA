// Engineering ablation on the original T2X baseline. No final eight-case claim.
#include "../../External/RenderDoc/renderdoc_app.h"
class BenchItemTemporalContrast : public AutoBenchToolWorkItem
{
    struct Config { const char* name; int kind; float threshold; bool pattern = true; };
    std::vector<Config> m_configs;
    bool m_capture, m_execution, m_done = false, m_started = false, m_failed = false;
    bool m_warp = false;
    bool m_jitterAblation = false, m_savedPattern = true;
    bool m_historyFilter = false, m_deJitter = false;
    int m_pairOrder = -1;
    bool m_counterCapture = false, m_counterCaptureActive = false;
    RENDERDOC_API_1_6_0* m_renderdoc = nullptr;
    bool m_costFocused = false, m_preconditionReady = false;
    double m_preconditionUntil = 0;
    int m_frames, m_warmup, m_repeats, m_run = 0, m_slot = 0, m_frame = 0;
    int m_savedKind = 0, m_savedPreset = 0;
    float m_savedThreshold = 0;
    CMAA2Sample::SceneSelectionType m_scene;
    std::vector<double> m_total, m_spatial, m_resolve, m_whole, m_wall;
    double m_lastTick = 0;
    Config Current() const {
        const int i = (m_run % 2) ? int(m_configs.size())-1-m_slot : m_slot;
        return m_configs[i];
    }
    void Configure() {
        auto smaa = m_parent.GetSMAA();
        const auto c = Current();
        m_parent.Settings().CurrentAAOption = c.kind==4 ?
            CMAA2Sample::AAType::SuperSampleReference : CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        smaa->SetTemporalContrast(c.kind==4?0:c.kind,c.threshold);
        smaa->SetTemporalSamplePatternEnabled(c.pattern);
        smaa->ResetTemporalHistory();
        m_frame = -m_warmup;
        m_total.clear();m_spatial.clear();m_resolve.clear();m_whole.clear();m_wall.clear();
    }
    static double Time(const char* name) {
        auto p = vaProfiler::GetInstancePtr();
        const auto node = p ? p->FindNode(name) : nullptr;
        return node ? node->GetFrameLastTotalTimeGPU()*1000.0 : 0.0;
    }
    void ReportSamples(AutoBenchTool& tool, const char* metric, std::vector<double> values) {
        if(values.size()!=size_t(m_frames)) m_failed=true;
        if(values.empty()) return;
        double mean=0; for(double v:values)mean+=v; mean/=values.size();
        std::sort(values.begin(),values.end());
        const auto c=Current();
        tool.ReportAddRowValues({"timing", c.name, std::to_string(m_run), metric,
            std::to_string(values.size()),vaStringTools::Format("%.9f",mean),
            vaStringTools::Format("%.9f",values[size_t((values.size()-1)*0.95)]),
            vaStringTools::Format("%.9f",c.threshold)});
        if(m_execution) {
            double variance=0;for(double v:values)variance+=(v-mean)*(v-mean);
            const size_t tailCount=vaMath::Max(size_t(1),(values.size()+99)/100);
            double tailMean=0;for(size_t i=values.size()-tailCount;i<values.size();++i)tailMean+=values[i];tailMean/=tailCount;
            tool.ReportAddRowValues({"distribution",c.name,std::to_string(m_run),metric,
                std::to_string(values.size()),vaStringTools::Format("%.9f",(values[(values.size()-1)/2]+values[values.size()/2])*0.5),
                vaStringTools::Format("%.9f",sqrt(variance/vaMath::Max(size_t(1),values.size()-1))),
                vaStringTools::Format("%.9f",values[size_t((values.size()-1)*0.99)]),
                vaStringTools::Format("%.9f",strcmp(metric,"WallFrame")==0?1000.0/mean:0),
                vaStringTools::Format("%.9f",strcmp(metric,"WallFrame")==0?1000.0/tailMean:0)});
        }
    }
public:
    BenchItemTemporalContrast(CMAA2Sample& parent,bool capture,bool minecraft,int frames,int repeats,bool quality=false,bool execution=false,bool dependency=false,bool locality=false,bool cost=false,bool costFocused=false,bool warp=false,int pairOrder=-1,bool counterCapture=false,bool jitterAblation=false,bool historyFilter=false,bool deJitter=false)
        :AutoBenchToolWorkItem(parent),m_capture(capture),m_execution(execution||dependency||locality||cost||warp||pairOrder>=0),m_frames(frames),
         m_warmup(capture?60:300),m_repeats(capture?1:repeats),
         m_scene(minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro)
    {
        m_warp=warp;
        m_pairOrder=pairOrder;
        m_costFocused=costFocused||(warp&&!capture)||pairOrder>=0||((historyFilter||deJitter)&&!capture);
        m_configs={{"O-T2X-R",0,0},{"ABL-Contrast-All-R",1,0},
            {"ABL-Contrast-0005-R",1,0.005f},{"ABL-Contrast-001-R",1,0.01f},
            {"ABL-Contrast-002-R",1,0.02f},{"ABL-Contrast-None-R",1,2.0f}};
        if(capture) {
            m_configs.push_back({"DBG-CurrentSpatial-R",3,0});
            m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
            m_configs.push_back({"O-T2X-R-Repeat",0,0});
        }
        if(quality) {
            m_configs={{"O-T2X-R",0,0},{"DBG-ContrastMask-0005-R",2,0.005f},
                {"DBG-ContrastMask-001-R",2,0.01f},{"DBG-ContrastMask-002-R",2,0.02f},
                {"SS-Reference",4,0}};
        }
        if(execution) {
            m_configs={{"O-T2X-R",0,0},{"ABL-NativeSM5-R",5,0},
                {"ABL-Lod-R",6,0},{"ABL-CurrentFirst-R",7,0},
                {"ABL-Contrast-All-R",1,0},{"ABL-Contrast-001-R",1,0.01f},
                {"ABL-Structured-001-R",8,0.01f},{"ABL-Flatten-001-R",9,0.01f},
                {"ABL-PrefetchVelocity-001-R",10,0.01f}};
            if(capture) {
                m_configs.push_back({"DBG-CurrentSpatial-R",3,0});
                m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
            }
        }
        if(dependency) {
            m_configs={{"O-T2X-R",0,0},{"ABL-Contrast-001-R",1,0.01f},
                {"ABL-Structured-001-R",8,0.01f},{"ABL-LoadCurrent-001-R",11,0.01f},
                {"ABL-LoadCurrentVelocity-001-R",12,0.01f}};
            if(capture) {
                m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
                m_configs.push_back({"DBG-LoadContrastMask-001-R",13,0.01f});
            }
        }
        if(locality) {
            m_configs={{"O-T2X-R",0,0},{"ABL-Contrast-All-R",1,0},{"ABL-Contrast-001-R",1,0.01f},
                {"DIAG-Stripe1-Branch-R",14,0},{"DIAG-Stripe32-Branch-R",14,5},
                {"DIAG-Stripe1-Flatten-R",15,0},{"DIAG-Stripe32-Flatten-R",15,5}};
            if(capture) {
                m_configs.push_back({"DBG-CurrentSpatial-R",3,0});
                m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
            }
        }
        if(cost) {
            m_configs={{"O-T2X-R",0,0},{"ABL-Contrast-001-R",1,0.01f},{"ABL-Flatten-001-R",9,0.01f},
                {"ABL-ScalarWeight-001-R",16,0.01f},{"ABL-ScalarReassociated-001-R",17,0.01f},
                {"ABL-BranchReassociated-001-R",18,0.01f},{"ABL-HistoryLoad-001-R",19,0.01f},
                {"ABL-SelectorAny-001-R",20,0.01f},{"ABL-FixedThreshold-001-R",21,0.01f},
                {"ABL-ScalarFixedThreshold-001-R",22,0.01f}};
            if(capture) m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
        }
        if(costFocused) {
            // Native is in the middle in both forward/reverse order. No shader change.
            m_configs={{"ABL-Contrast-001-R",1,0.01f},{"O-T2X-R",0,0},{"ABL-ScalarWeight-001-R",16,0.01f}};
        }
        if(warp) {
            m_configs={{"ABL-Contrast-001-R",1,0.01f},{"O-T2X-R",0,0},
                {"ABL-NvWarp-001-R",23,0.01f},{"ABL-ScalarWeight-001-R",16,0.01f}};
            if(capture) {
                m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
                m_configs.push_back({"DBG-NvWarpMask-001-R",24,0.01f});
            }
        }
        if(pairOrder>=0) {
            m_configs={{"O-T2X-R",0,0},{"ABL-ScalarWeight-001-R",16,0.01f}};
            if(pairOrder==1)std::reverse(m_configs.begin(),m_configs.end());
            m_repeats=1;
        }
        if(counterCapture) {
            m_counterCapture=true;m_capture=true;m_warmup=300;m_repeats=1;
            m_configs={{"O-T2X-R",0,0},{"ABL-Contrast-001-R",1,0.01f},{"ABL-ScalarWeight-001-R",16,0.01f}};
        }
        if(jitterAblation) {
            m_jitterAblation=true;
            m_configs={{"O-T2X-R",0,0,true},{"ABL-ScalarWeight-001-R",16,0.01f,true},
                {"ABL-Standard-PatternOff-R",0,0,false},{"ABL-ScalarWeight-001-PatternOff-R",16,0.01f,false},
                {"DBG-ContrastMask-001-R",2,0.01f,true},{"DBG-ContrastMask-001-PatternOff-R",2,0.01f,false},
                {"DBG-CurrentSpatial-R",3,0,true},{"DBG-CurrentSpatial-PatternOff-R",3,0,false},
                {"ABL-Standard-PatternOff-R-Repeat",0,0,false},{"ABL-ScalarWeight-001-PatternOff-R-Repeat",16,0.01f,false}};
        }
        if(historyFilter) {
            m_historyFilter=true;m_execution=true;
            m_configs={{"O-T2X-R",0,0},{"ABL-HistoryPoint-Control-R",6,0},{"ABL-HistoryLinear-R",25,0},
                {"ABL-ScalarWeight-001-R",16,0.01f},{"ABL-ScalarHistoryLinear-001-R",26,0.01f}};
            if(capture) {
                m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
                m_configs.push_back({"DBG-CurrentSpatial-R",3,0});
                m_configs.push_back({"ABL-HistoryLinear-R-Repeat",25,0});
                m_configs.push_back({"ABL-ScalarHistoryLinear-001-R-Repeat",26,0.01f});
            }
        }
        if(deJitter) {
            m_deJitter=true;m_execution=true;
            m_configs={{"O-T2X-R",0,0},{"ABL-ScalarWeight-001-R",16,0.01f},
                {"ABL-ScalarCurrentLinear-001-R",27,0.01f},{"ABL-CurrentDeJitter-R",28,0},
                {"ABL-ScalarDeJitter-001-R",29,0.01f}};
            if(capture) {
                m_configs.push_back({"DBG-ContrastMask-001-R",2,0.01f});
                m_configs.push_back({"DBG-CurrentSpatial-R",3,0});
                m_configs.push_back({"DBG-DeJitterMask-001-R",30,0.01f});
                m_configs.push_back({"DBG-DeJitterSpatial-R",31,0});
                m_configs.push_back({"ABL-CurrentDeJitter-R-Repeat",28,0});
                m_configs.push_back({"ABL-ScalarDeJitter-001-R-Repeat",29,0.01f});
            }
        }
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        const double wallMs=(now-m_lastTick)*1000.0;m_lastTick=now;
        if(!m_started) {
            m_started=true;
            auto smaa=m_parent.GetSMAA();
            m_savedKind=smaa->GetTemporalContrastKind();
            m_savedPattern=smaa->GetTemporalSamplePatternEnabled();
            m_savedThreshold=smaa->GetTemporalContrastThreshold();
            m_savedPreset=int(smaa->GetSettings().Preset);
            smaa->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_scene;
            m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
            m_parent.SetRequireDeterminism(true);
            m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);
            vaUIManager::GetInstance().SetConsoleVisible(false);
            tool.ReportStart();
            if(m_counterCapture) {
                HMODULE module=GetModuleHandleA("renderdoc.dll");
                auto getAPI=module?reinterpret_cast<pRENDERDOC_GetAPI>(GetProcAddress(module,"RENDERDOC_GetAPI")):nullptr;
                if(!getAPI || getAPI(eRENDERDOC_API_Version_1_6_0,reinterpret_cast<void**>(&m_renderdoc))!=1) {
                    tool.ReportAddText("RenderDoc API unavailable\r\nAggregate: FAIL\r\n");
                    tool.ReportFinish();m_done=true;smaa->GetSettings().Preset=vaSMAAWrapper::Preset(m_savedPreset);return;
                }
                tool.ReportAddText("Purpose: RenderDoc frame 90 capture for replay counters; no live timing claim or PNG.\r\n");
            }
            if(m_warp) {
                bool supported=smaa->SupportsTemporalWarp();
                tool.ReportAddText(supported?"NVAPI VOTE_ANY supported: 1\r\n":"NVAPI VOTE_ANY supported: 0\r\nAggregate: FAIL\r\n");
                if(!supported) { tool.ReportFinish();m_done=true;smaa->GetSettings().Preset=vaSMAAWrapper::Preset(m_savedPreset);return; }
                tool.ReportAddText("Same pixel selector; warp-uniform history execution; per-pixel weight masking. NVIDIA-only diagnostic.\r\n");
            }
            tool.ReportAddText("Native Standard temporal contrast engineering gate\r\n");
            if(m_historyFilter)tool.ReportAddText("History filter gate: paired pattern On, same spatial-frame history and adaptive weight formula. Linear filters history RGBA including velocity alpha. No new pass/resource/sample instruction.\r\n");
            if(m_deJitter)tool.ReportAddText("Current de-jitter gate: one linear current read at UV plus current screen jitter; Point history and original velocity UV; paired pattern On; spatial-frame history. Selector and current alpha change. No extra pass/texture/sample instruction.\r\n");
            if(m_jitterAblation)tool.ReportAddText("Pattern ablation: On=paired projection jitter/subsample indices; Off=zero jitter/1X indices. Spatial-frame history and camera reprojection preserved. Diagnostic Off modes are not official T2X.\r\n");
            tool.ReportAddText(m_capture?"Purpose: quality/correctness capture; no GPU performance claim\r\n":"Purpose: paired GPU performance; no PNG or candidate readback\r\n");
            tool.ReportAddText(vaStringTools::Format("Scene: %s\r\nFrames: %d\r\nWarmup: %d\r\nRepeats: %d\r\n",
                m_scene==CMAA2Sample::SceneSelectionType::MinecraftLostEmpire?"minecraft":"bistro",m_frames,m_warmup,m_repeats));
            tool.ReportAddText("Profile: original flythrough t=2, 60 still + 120 moving + 60 still; 240-frame period. Fixed 60 Hz. Spatial history, paired jitter, camera reprojection. History and jitter reset at frame 0 after resource warmup; first 60 captured frames settle at the same pose.\r\n");
            tool.ReportAddText(vaStringTools::Format("SS-Reference if requested: %dx linear resolution, %dx%d within-frame grid, %dx MSAA; no temporal history. MIP bias 0.95, sharpen 0.12, derivative bias 0.20 (baseline defaults). Spatial reference proxy, not absolute temporal ground truth.\r\n",
                m_parent.GetSSResScale(),m_parent.GetSSGridRes(),m_parent.GetSSGridRes(),m_parent.GetSSMSAASampleCount()));
            if(!m_capture)tool.ReportAddRowValues({"kind","mode","run","metric","samples","mean_ms","p95_ms","threshold"});
            if(m_execution)tool.ReportAddText("distribution columns: mode, run, metric, samples, median_ms, sample_std_ms, p99_ms, wall_fps, wall_1pct_low_fps (slowest ceil(N/100) intervals). Non-wall FPS fields are 0/not applicable.\r\n");
            tool.ReportAddText("DIAG-Stripe modes if present: threshold column is log2(stripe width), not luma threshold. Synthetic 50% coverage diagnostic, not a quality algorithm or measured hardware branch efficiency.\r\n");
            if(m_pairOrder>=0) {
                tool.ReportAddText(m_pairOrder==0?"Independent process pair order: AB\r\n":"Independent process pair order: BA\r\n");
                tool.ReportAddText("Common preconditioning: O-T2X-R, 30 seconds, static t=2; then 300-frame per-mode warmup. A=O-T2X-R; B=ABL-ScalarWeight-001-R.\r\n");
            } else if(m_costFocused) {
                tool.ReportAddText("Focused same-selector confirmation: 30 seconds unmeasured rendering before the ordinary 300-frame per-mode warmup; alternating forward/reverse mode order (3-mode cost gate keeps native in the middle). No capture or algorithm change.\r\n");
            }
            Configure();
            if(m_pairOrder>=0) {
                smaa->SetTemporalContrast(0,0);
                smaa->ResetTemporalHistory();
            }
        } else {
            if(m_costFocused && !m_preconditionReady) {
                m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f);
                if(m_preconditionUntil==0)m_preconditionUntil=now+30.0;
                if(now<m_preconditionUntil)return;
                m_preconditionReady=true;
                tool.ReportAddText(vaStringTools::Format("Focused preconditioning elapsed seconds: %.6f\r\n",now-m_preconditionUntil+30.0));
                Configure(); // Discard preconditioning samples/history before ordinary warmup.
                return;
            }
            if(!m_capture && m_frame>=0) {
                const double t=Time("SMAA"),s=Time("SMAASpatial"),r=Time("SMAATemporalResolve");
                if(t>0 && s>0 && r>0) {m_total.push_back(t);m_spatial.push_back(s);m_resolve.push_back(r);}
                else m_failed=true;
                if(m_execution) {
                    const double w=Time("WholeFrame");
                    if(w>0 && wallMs>0) {m_whole.push_back(w);m_wall.push_back(wallMs);}
                    else m_failed=true;
                }
            }
            ++m_frame;
            if(m_frame>=m_frames) {
                if(!m_capture) {ReportSamples(tool,"SMAA",m_total);ReportSamples(tool,"Spatial",m_spatial);ReportSamples(tool,"Resolve",m_resolve);
                    if(m_execution) {ReportSamples(tool,"WholeFrame",m_whole);ReportSamples(tool,"WallFrame",m_wall);}}
                if(++m_slot==int(m_configs.size())) {m_slot=0;++m_run;}
                if(m_run==m_repeats) {
                    tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");
                    tool.ReportFinish();m_done=true;
                    m_parent.GetSMAA()->SetTemporalContrast(m_savedKind,m_savedThreshold);
                    m_parent.GetSMAA()->SetTemporalSamplePatternEnabled(m_savedPattern);
                    m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::Preset(m_savedPreset);
                    return;
                }
                Configure();
            }
        }
        // Loading may render additional frames while Tick is held. Seed the
        // captured timeline explicitly so every mode starts with jitter S0.
        if(m_frame==0)m_parent.GetSMAA()->ResetTemporalHistory();
        const int phase=m_frame<0?0:m_frame%240;
        const float t=2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f;
        m_parent.GetFlythroughCameraController()->SetPlayTime(t);
        if(m_counterCapture && m_frame==90) {
            const auto path=tool.ReportGetDir()+vaStringTools::SimpleWiden(Current().name);
            m_renderdoc->SetCaptureFilePathTemplate(vaStringTools::SimpleNarrow(path).c_str());
            m_renderdoc->StartFrameCapture(nullptr,nullptr);
            m_counterCaptureActive=true;
        }
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& context,
        const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(!m_capture || m_frame<0 || m_done)return;
        if(m_counterCapture) {
            if(m_counterCaptureActive) {
                const bool ok=m_renderdoc->EndFrameCapture(nullptr,nullptr)!=0;
                m_failed=m_failed||!ok;m_counterCaptureActive=false;
                tool.ReportAddRowValues({"renderdoc_capture",Current().name,std::to_string(m_frame),ok?"PASS":"FAIL"});
            }
            return;
        }
        const auto c=Current();
        if(m_jitterAblation || m_historyFilter || m_deJitter) {
            auto smaa=m_parent.GetSMAA();
            bool ok=smaa->GetTemporalSamplePatternEnabled()==c.pattern;
            for(int k=0;k<4;k++) {
                const float expected=c.pattern && k<3 ? float(m_frame%2+1) : 0.0f;
                ok=ok && smaa->GetTemporalSubsampleIndexForDiagnostics(k)==expected;
            }
            const auto jitter=smaa->GetTemporalJitterOffset();
            ok=ok && (c.pattern ? (fabs(jitter.x)==0.25f && fabs(jitter.y)==0.25f) : (jitter.x==0 && jitter.y==0));
            m_failed=m_failed||!ok;
            tool.ReportAddRowValues({"pattern_check",c.name,std::to_string(m_frame),c.pattern?"On":"Off",ok?"PASS":"FAIL"});
        }
        const auto dir=tool.ReportGetDir()+vaStringTools::SimpleWiden(c.name)+L"\\";
        vaFileTools::EnsureDirectoryExists(dir);
        const auto path=dir+vaStringTools::Format(L"frame_%05d.png",m_frame);
        if(!color->SaveToPNGFile(context,path))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_run*m_configs.size()+m_slot)/float(m_repeats*m_configs.size());}
};

static bool QueueTemporalContrastExperiment(CMAA2Sample& parent,AutoBenchTool& tool) {
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()) {
        if(_wcsicmp(p.first.c_str(),L"smaaShaderFailureTest")==0) {
            VA_LOG_ERROR("EXPECTED_SHADER_FAILURE_TEST");
            auto shader=VA_RENDERING_MODULE_CREATE_SHARED(vaPixelShader,parent.GetRenderDevice());
            if(p.second==L"file")
                shader->CreateShaderFromFile(vaCore::GetExecutableDirectory()+L"../../Tools/SMAA/fixtures/invalid_shader.hlsl","ps_5_0","main",{},false);
            else
                shader->CreateShaderFromBuffer("float4 main():SV_Target{return intentionally_missing_symbol;}","ps_5_0","main",{},false);
            return true; // shared deleter joins; expected compile failure makes process exit nonzero.
        }
        if(_wcsicmp(p.first.c_str(),L"smaaShaderLifetimeTest")==0) {
            tool.AddTask(std::make_shared<BenchItemShaderLifetime>(parent));
            return true;
        }
        bool capture=_wcsicmp(p.first.c_str(),L"smaaTemporalContrastCapture")==0;
        bool bench=_wcsicmp(p.first.c_str(),L"smaaTemporalContrastBenchmark")==0;
        bool smoke=_wcsicmp(p.first.c_str(),L"smaaTemporalContrastSmoke")==0;
        bool quality=_wcsicmp(p.first.c_str(),L"smaaTemporalContrastQualityCapture")==0;
        bool jitterAblation=_wcsicmp(p.first.c_str(),L"smaaTemporalContrastJitterCapture")==0;
        capture=capture||jitterAblation;
        bool deJitterCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalDeJitterCapture")==0;
        bool deJitterSmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalDeJitterSmoke")==0;
        bool deJitterBenchmark=_wcsicmp(p.first.c_str(),L"smaaTemporalDeJitterBenchmark")==0;
        bool deJitter=deJitterCapture||deJitterSmoke||deJitterBenchmark;
        capture=capture||deJitterCapture;smoke=smoke||deJitterSmoke;bench=bench||deJitterBenchmark;
        bool historyCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalHistoryFilterCapture")==0;
        bool historySmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalHistoryFilterSmoke")==0;
        bool historyBenchmark=_wcsicmp(p.first.c_str(),L"smaaTemporalHistoryFilterBenchmark")==0;
        bool historyFilter=historyCapture||historySmoke||historyBenchmark;
        capture=capture||historyCapture;smoke=smoke||historySmoke;bench=bench||historyBenchmark;
        bool executionCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalExecutionCapture")==0;
        bool executionBench=_wcsicmp(p.first.c_str(),L"smaaTemporalExecutionBenchmark")==0;
        bool executionSmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalExecutionSmoke")==0;
        bool execution=executionCapture||executionBench||executionSmoke;
        capture=capture||executionCapture;bench=bench||executionBench;smoke=smoke||executionSmoke;
        bool dependencyCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalDependencyCapture")==0;
        bool dependencyBench=_wcsicmp(p.first.c_str(),L"smaaTemporalDependencyBenchmark")==0;
        bool dependencySmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalDependencySmoke")==0;
        bool dependency=dependencyCapture||dependencyBench||dependencySmoke;
        capture=capture||dependencyCapture;bench=bench||dependencyBench;smoke=smoke||dependencySmoke;
        bool localityCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalLocalityCapture")==0;
        bool localityBench=_wcsicmp(p.first.c_str(),L"smaaTemporalLocalityBenchmark")==0;
        bool localitySmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalLocalitySmoke")==0;
        bool locality=localityCapture||localityBench||localitySmoke;
        capture=capture||localityCapture;bench=bench||localityBench;smoke=smoke||localitySmoke;
        bool costCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalCostCapture")==0;
        bool costFocusedBench=_wcsicmp(p.first.c_str(),L"smaaTemporalCostFocusedBenchmark")==0;
        bool costFocusedSmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalCostFocusedSmoke")==0;
        bool costFocused=costFocusedBench||costFocusedSmoke;
        bool costBench=_wcsicmp(p.first.c_str(),L"smaaTemporalCostBenchmark")==0||costFocusedBench;
        bool costSmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalCostSmoke")==0||costFocusedSmoke;
        bool cost=costCapture||costBench||costSmoke;
        capture=capture||costCapture;bench=bench||costBench;smoke=smoke||costSmoke;
        bool warpCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalWarpCapture")==0;
        bool warpBench=_wcsicmp(p.first.c_str(),L"smaaTemporalWarpBenchmark")==0;
        bool warpSmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalWarpSmoke")==0;
        bool warp=warpCapture||warpBench||warpSmoke;
        capture=capture||warpCapture;bench=bench||warpBench;smoke=smoke||warpSmoke;
        bool pairBench=_wcsicmp(p.first.c_str(),L"smaaTemporalPairBenchmark")==0;
        bool pairSmoke=_wcsicmp(p.first.c_str(),L"smaaTemporalPairSmoke")==0;
        bool pair=pairBench||pairSmoke;
        bench=bench||pairBench;smoke=smoke||pairSmoke;
        bool counterCapture=_wcsicmp(p.first.c_str(),L"smaaTemporalCounterCapture")==0;
        capture=capture||counterCapture;
        if(!capture && !bench && !smoke && !quality)continue;
        std::wistringstream input(p.second);std::wstring scene;input>>scene;
        if(scene!=L"bistro" && scene!=L"minecraft") {VA_LOG_ERROR("Expected bistro or minecraft");return true;}
        int pairOrder=-1;
        if(pair) {
            std::wstring order,extra;input>>order;
            if((order!=L"AB" && order!=L"BA") || (input>>extra)) {VA_LOG_ERROR("Expected pair order AB or BA and no extra arguments");return true;}
            pairOrder=order==L"AB"?0:1;
        }
        int qualityFrames=240;
        if(quality) {input>>qualityFrames;qualityFrames=vaMath::Clamp(qualityFrames,1,240);}
        tool.AddTask(std::make_shared<BenchItemTemporalContrast>(parent,capture||quality,scene==L"minecraft",counterCapture?121:quality?qualityFrames:capture?240:smoke?240:4800,(smoke||pair)?1:(historyFilter||deJitter)?4:(costFocused||warp)?5:3,quality,execution,dependency,locality,cost,costFocused,warp,pairOrder,counterCapture,jitterAblation,historyFilter,deJitter));
        return true;
    }
    return false;
}
