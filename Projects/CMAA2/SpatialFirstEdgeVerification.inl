#include <map>
#include <cmath>
#include <chrono>
// Item 6 only: native spatial SMAA remains enabled for full and selective temporal.
class BenchItemSpatialFirstEdgeVerification : public AutoBenchToolWorkItem {
    struct Mode {const char* name; CMAA2Sample::AAType type; bool selective=false;};
    std::vector<Mode> m_modes;
    bool m_capture,m_minecraft,m_started=false,m_done=false,m_failed=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames=4800,m_repeats=4;
    double m_until=0;
    vaSMAAWrapper::Preset m_savedPreset=vaSMAAWrapper::PRESET_HIGH;
    std::map<std::string,std::vector<double>> m_samples;
    std::chrono::steady_clock::time_point m_lastTick=std::chrono::steady_clock::now();
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    void Configure(){m_parent.Settings().CurrentAAOption=Current().type;m_parent.GetSMAA()->SetSpatialFirstEdgeEnabled(Current().selective);m_parent.GetSMAA()->ResetTemporalHistory();m_frame=m_capture?-60:-300;m_samples.clear();}
    static double Time(const char* name){auto p=vaProfiler::GetInstancePtr();auto n=p?p->FindNode(name):nullptr;return n?n->GetFrameLastTotalTimeGPU()*1000.0:0;}
    void Summarize(AutoBenchTool& tool,const char* metric,std::vector<double> v){
        if(v.size()!=size_t(m_measureFrames)){m_failed=true;return;}
        double mean=0;for(double x:v)mean+=x;mean/=v.size();std::sort(v.begin(),v.end());
        double variance=0;for(double x:v)variance+=(x-mean)*(x-mean);
        tool.ReportAddRowValues({"timing",Current().name,std::to_string(m_run),metric,std::to_string(v.size()),
            vaStringTools::Format("%.9f",mean),vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.95)]),
            vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.99)]),vaStringTools::Format("%.9f",v[v.size()/2]),vaStringTools::Format("%.9f",sqrt(variance/(v.size()-1)))});
        if(std::string(metric)=="WallFrame"){
            size_t n=size_t(ceil(v.size()*.01));double slow=0;for(size_t i=v.size()-n;i<v.size();++i)slow+=v[i];slow/=n;
            tool.ReportAddRowValues({"rate",Current().name,std::to_string(m_run),vaStringTools::Format("%.9f",1000/mean),vaStringTools::Format("%.9f",1000/slow),std::to_string(v.size())});
        }
    }
public:
    BenchItemSpatialFirstEdgeVerification(CMAA2Sample& p,bool capture,bool minecraft,bool smoke=false):AutoBenchToolWorkItem(p),m_capture(capture),m_minecraft(minecraft){
        m_measureFrames=smoke?240:4800;m_repeats=smoke?1:4;
        m_modes={{"O-T2X-R",CMAA2Sample::AAType::SMAA_T2x_Reprojected,false},
                 {"ABL-SpatialFirstEdge-T2X-R",CMAA2Sample::AAType::SMAA_T2x_Reprojected,true}};
        if(capture){m_modes.push_back({"AA-Off",CMAA2Sample::AAType::None,false});m_modes.push_back({"O-1X",CMAA2Sample::AAType::SMAA,false});m_modes.push_back({"ABL-SpatialFirstEdge-T2X-R-Repeat",CMAA2Sample::AAType::SMAA_T2x_Reprojected,true});}
    }
    void Tick(AutoBenchTool& tool,float) override {
        auto now=std::chrono::steady_clock::now();double wall=std::chrono::duration<double,std::milli>(now-m_lastTick).count();m_lastTick=now;
        if(!m_started){
            m_started=true;m_savedPreset=m_parent.GetSMAA()->GetSettings().Preset;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();tool.ReportAddText("Item 6 from e14f122; all three native spatial SMAA passes retained. Native first-edge RG>0 gates native temporal math; no extra detection/prepare/copy/compact pass. Native spatial-frame history and paired projection jitter retained. Camera/depth reprojection only.\r\n");
            tool.ReportAddText(m_capture?"Capture: 240 frames per mode; final/current PNG, native edge and spatial-input probes. No timing claim.\r\n":"Timing: 30s precondition; 300 warmup; 4800 frames x 4 alternating repeats (Smoke 240 x 1). No image/mask readback. WholeFrame/SMAA/camera/spatial/resolve GPU scopes; steady-clock wall frame. Rate = 1000/mean; 1% low = 1000/mean slowest ceil(N*.01) intervals.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra, fixed60Hz; t=2+clamp(phase-60,0,120)/60; 240-frame still/move/still cycle. Reset history at each cycle wrap.\r\n");
            Configure();if(!m_capture)m_until=app.GetTimeFromStart()+30;
        }else if(m_until!=0){
            if(m_parent.GetApplication().GetTimeFromStart()<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}
            m_until=0;Configure();
        }else{
            if(!m_capture&&m_frame>=0){
                for(auto name:{"WholeFrame","SMAA","SF_CameraVelocity","SF_Spatial","SF_Resolve"}){
                    double value=Time(name);if(value>0 && std::isfinite(value))m_samples[name].push_back(value);else m_failed=true;
                }
                if(wall>0&&std::isfinite(wall))m_samples["WallFrame"].push_back(wall);else m_failed=true;
            }
            ++m_frame;if(m_frame>=(m_capture?240:m_measureFrames)){
                if(!m_capture){for(auto& metric:m_samples)Summarize(tool,metric.first.c_str(),metric.second);}
                if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                if(m_run==(m_capture?1:m_repeats)){
                    tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
                    m_parent.GetSMAA()->GetSettings().Preset=m_savedPreset;m_parent.GetSMAA()->SetSpatialFirstEdgeEnabled(false);
                    m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();return;
                }
                Configure();
            }
        }
        const int phase=m_frame<0?0:m_frame%240;
        if(m_frame>=0 && phase==0)m_parent.GetSMAA()->ResetTemporalHistory();
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(!m_capture||m_frame<0||m_done)return;const auto c=Current();const auto s=m_parent.GetSMAA();
        const bool temporal=c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        const bool ok=s->GetTemporalModeEnabled()==temporal&&s->GetTemporalReprojectionEnabled()==temporal&&s->GetSpatialFirstEdgeEnabled()==c.selective;
        m_failed=m_failed||!ok;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),temporal?"TemporalOn":"TemporalOff",temporal?"CameraR":"NoR",ok?"PASS":"FAIL"});
        const auto dir=tool.ReportGetDir()+vaStringTools::SimpleWiden(c.name)+L"\\";vaFileTools::EnsureDirectoryExists(dir);
        const auto prefix=dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame));
        const bool probe=m_frame==0||m_frame==1||m_frame==59||m_frame==60||m_frame==61||m_frame==100||m_frame==179||m_frame==180||m_frame==181||m_frame==239;
        const bool primary=std::string(c.name)=="ABL-SpatialFirstEdge-T2X-R";
        if(temporal && (primary || !c.selective || probe))
            if(!s->SaveSpatialEdgeSnapshot(ctx,prefix,primary||probe,probe))m_failed=true;
        if(!color->SaveToPNGFile(ctx,prefix+L".png"))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueSpatialFirstEdgeVerification(CMAA2Sample& parent,AutoBenchTool& tool){
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()){
        const bool capture=_wcsicmp(p.first.c_str(),L"smaaSpatialFirstEdgeCapture")==0;
        const bool performance=_wcsicmp(p.first.c_str(),L"smaaSpatialFirstEdgeBenchmark")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaSpatialFirstEdgeSmoke")==0;
        if(!capture&&!performance&&!smoke)continue;std::wistringstream input(p.second);std::wstring scene;input>>scene;
        if(scene!=L"bistro"&&scene!=L"minecraft"){VA_LOG_ERROR("Expected bistro or minecraft");return;}
        tool.AddTask(std::make_shared<BenchItemSpatialFirstEdgeVerification>(parent,capture,scene==L"minecraft",smoke));return;
    }
}
