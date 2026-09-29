#include <map>
#include <cmath>
#include <chrono>
#include <fstream>
#include <wincrypt.h>
#pragma comment(lib,"advapi32.lib")
// Item 5 only; reuse the item-6 diagnostic harness, not its spatial implementation.
class BenchItemEdgePatternVerification : public AutoBenchToolWorkItem {
    struct Mode {const char* name; CMAA2Sample::AAType type; bool selective,pattern,keep;};
    std::vector<Mode> m_modes;
    bool m_capture,m_minecraft,m_started=false,m_done=false,m_failed=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames=4800,m_repeats=4;
    double m_until=0;
    std::wstring m_output;
    vaSMAAWrapper::Preset m_savedPreset=vaSMAAWrapper::PRESET_HIGH;
    bool m_savedPattern=true,m_savedTemporalOnly=false,m_savedReference=false;
    int m_savedEdgeMode=0;
    std::map<std::string,std::vector<double>> m_samples;
    std::chrono::steady_clock::time_point m_lastTick=std::chrono::steady_clock::now();
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    static std::string Hash(const std::wstring& path){
        HCRYPTPROV provider=0;HCRYPTHASH hash=0;std::ifstream in(path,std::ios::binary);if(!in)return "ERROR";
        if(!CryptAcquireContext(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT))return "ERROR";
        if(!CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){CryptReleaseContext(provider,0);return "ERROR";}
        char buffer[65536];bool ok=true;while(in){in.read(buffer,sizeof(buffer));if(in.gcount())ok=ok&&CryptHashData(hash,reinterpret_cast<BYTE*>(buffer),DWORD(in.gcount()),0);}
        BYTE digest[32];DWORD n=32;ok=ok&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)&&n==32;
        CryptDestroyHash(hash);CryptReleaseContext(provider,0);if(!ok)return "ERROR";
        std::string result;for(BYTE b:digest)result+=vaStringTools::Format("%02x",int(b));return result;
    }
    void Configure(){
        const auto c=Current();auto s=m_parent.GetSMAA();m_parent.Settings().CurrentAAOption=c.type;
        const bool raw=c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected && std::string(c.name)!="O-T2X-R";
        s->SetTemporalOnlyControl(raw);s->SetFirstEdgeOnlyMode(raw?(c.selective?2:1):0);s->SetTemporalSamplePatternEnabled(c.pattern);s->ResetTemporalHistory();
        m_frame=m_capture?-60:-300;m_samples.clear();
    }
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
    BenchItemEdgePatternVerification(CMAA2Sample& p,bool capture,bool minecraft,bool smoke,std::wstring output):AutoBenchToolWorkItem(p),m_capture(capture),m_minecraft(minecraft),m_output(output){
        m_measureFrames=smoke?240:4800;m_repeats=smoke?1:4;
        const auto t=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        m_modes={{"DIAG-TemporalOnly-EdgeDetect-R",t,false,true,false},{"ABL-FirstEdge-TemporalOnly-R",t,true,true,false},
                 {"ABL-FirstEdge-TemporalOnly-Full-PatternOff-R",t,false,false,true},{"ABL-FirstEdge-TemporalOnly-PatternOff-R",t,true,false,true}};
        if(capture){m_modes.push_back({"O-T2X-R",t,false,true,false});m_modes.push_back({"AA-Off",CMAA2Sample::AAType::None,false,true,false});m_modes.push_back({"O-1X",CMAA2Sample::AAType::SMAA,false,true,false});m_modes.push_back({"ABL-FirstEdge-TemporalOnly-PatternOff-R-Repeat",t,true,false,false});}
    }
    void Tick(AutoBenchTool& tool,float) override {
        auto now=std::chrono::steady_clock::now();double wall=std::chrono::duration<double,std::milli>(now-m_lastTick).count();m_lastTick=now;
        if(!m_started){
            m_started=true;auto s=m_parent.GetSMAA();m_savedPreset=s->GetSettings().Preset;m_savedPattern=s->GetTemporalSamplePatternEnabled();m_savedTemporalOnly=s->GetTemporalOnlyControl();m_savedReference=s->GetTemporalOnlyReference();m_savedEdgeMode=s->GetFirstEdgeOnlyMode();s->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            const auto slash=report.find_last_of(L"\\/");const auto leaf=report.substr(slash+1);
            m_output+=L"/item5/"+std::wstring(m_minecraft?L"minecraft/":L"bistro/")+leaf+L"/";
            tool.ReportAddText("Item 5 pattern ablation from c51ca28 + 7c2feeb + a774772. Native first-edge detection, raw-current prepare, native temporal math, camera/depth R and raw-frame history retained. No spatial blend correction or area-index pass in raw path. Default pattern On unchanged; Off uses zero projection offset. Full controls also run edge detection to isolate selection. No dilation or additional pass.\r\n");
            tool.ReportAddText(m_capture?"Capture 240 frames; On and AAOff/1X controls hashed every frame, Off images retained, repeated Off hash bridge. No timing claim.\r\n":"Timing: hidden; 30s precondition; 300 warmup; 4800 frames x 4 alternating repeats (Smoke 240 x 1); no image/mask readback. WholeFrame/SMAA/camera/edge-detection/prepare/resolve GPU scopes and steady-clock wall intervals.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra, fixed60Hz; t=2+clamp(phase-60,0,120)/60; still60/move120/still60. Reset history at each cycle wrap.\r\n");
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            Configure();if(!m_capture)m_until=app.GetTimeFromStart()+30;
        }else if(m_until!=0){
            if(m_parent.GetApplication().GetTimeFromStart()<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}
            m_until=0;Configure();
        }else{
            if(!m_capture&&m_frame>=0){
                for(auto name:{"WholeFrame","SMAA","FE_CameraVelocity","FE_EdgeDetection","FE_Prepare","FE_Resolve"}){
                    double value=Time(name);if(value>0&&std::isfinite(value))m_samples[name].push_back(value);else m_failed=true;
                }
                if(wall>0&&std::isfinite(wall))m_samples["WallFrame"].push_back(wall);else m_failed=true;
            }
            ++m_frame;if(m_frame>=(m_capture?240:m_measureFrames)){
                if(!m_capture)for(auto& metric:m_samples)Summarize(tool,metric.first.c_str(),metric.second);
                if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                if(m_run==(m_capture?1:m_repeats)){
                    tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
                    auto s=m_parent.GetSMAA();s->GetSettings().Preset=m_savedPreset;s->SetFirstEdgeOnlyMode(m_savedEdgeMode);s->SetTemporalOnlyControl(m_savedTemporalOnly,m_savedReference);s->SetTemporalSamplePatternEnabled(m_savedPattern);
                    m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();return;
                }
                Configure();
            }
        }
        const int phase=m_frame<0?0:m_frame%240;
        if(m_frame>=0&&phase==0)m_parent.GetSMAA()->ResetTemporalHistory();
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(!m_capture||m_frame<0||m_done)return;const auto c=Current();const auto s=m_parent.GetSMAA();
        const bool temporal=c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        const auto jitter=s->GetLastTemporalProjectionOffset();const bool zeroIndices=s->GetTemporalOnlyControl()?true:s->HasZeroSubsampleIndices();
        const bool raw=temporal&&std::string(c.name)!="O-T2X-R";
        bool ok=s->GetTemporalOnlyControl()==raw&&!s->GetTemporalOnlyReference()&&s->GetTemporalModeEnabled()==temporal&&s->GetTemporalReprojectionEnabled()==temporal&&s->GetFirstEdgeOnlyMode()==(temporal&&std::string(c.name)!="O-T2X-R"?(c.selective?2:1):0)&&s->GetTemporalSamplePatternEnabled()==c.pattern;
        if(temporal)ok=ok&&(c.pattern?(abs(jitter.x)==.25f&&abs(jitter.y)==.25f&&(s->GetTemporalOnlyControl()||!zeroIndices)):(jitter.x==0&&jitter.y==0&&(s->GetTemporalOnlyControl()||zeroIndices)));
        m_failed=m_failed||!ok;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),temporal?"TemporalOn":"TemporalOff",c.pattern?"PatternOn":"PatternOff",vaStringTools::Format("%.2f",jitter.x),vaStringTools::Format("%.2f",jitter.y),s->GetTemporalOnlyControl()?"NoSpatialArea":(zeroIndices?"ZeroArea":"PairedArea"),ok?"PASS":"FAIL"});
        const auto dir=m_output+vaStringTools::SimpleWiden(c.name)+L"/";vaFileTools::EnsureDirectoryExists(dir);
        const auto prefix=dir+(c.keep?vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame)):L"rolling");
        const bool primary=c.keep&&c.selective;
        const bool probe=m_frame==0||m_frame==1||m_frame==59||m_frame==60||m_frame==61||m_frame==100||m_frame==179||m_frame==180||m_frame==181||m_frame==239;
        if(temporal&&!c.pattern&&c.keep){
            const auto snapshot=primary?prefix:dir+L"rolling-input";
            if(!s->SaveFirstEdgeSnapshot(ctx,snapshot,true))m_failed=true;
            const auto currentHash=Hash(snapshot+L"-current.png");if(currentHash=="ERROR")m_failed=true;
            tool.ReportAddRowValues({"current_hash",c.name,std::to_string(m_frame),currentHash});
            if(probe){const auto p=dir+vaStringTools::SimpleWiden(vaStringTools::Format("probe_%05d",m_frame));if(!s->SaveTemporalOnlyInputs(ctx,p))m_failed=true;}
        }
        if(!color->SaveToPNGFile(ctx,prefix+L".png"))m_failed=true;
        const auto hash=Hash(prefix+L".png");if(hash=="ERROR")m_failed=true;
        tool.ReportAddRowValues({"final_hash",c.name,std::to_string(m_frame),hash});
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueEdgePatternVerification(CMAA2Sample& parent,AutoBenchTool& tool){
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()){
        const bool capture=_wcsicmp(p.first.c_str(),L"smaaEdgePatternCapture")==0;
        const bool performance=_wcsicmp(p.first.c_str(),L"smaaEdgePatternBenchmark")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaEdgePatternSmoke")==0;
        if(!capture&&!performance&&!smoke)continue;std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;
        if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and an absolute output root without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemEdgePatternVerification>(parent,capture,scene==L"minecraft",smoke,output));return;
    }
}
