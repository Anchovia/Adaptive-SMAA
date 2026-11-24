// Validation harness for baseline/improved-smaa-demo (validation/improved-smaa-demo-equivalence only).
//   -improvedSmaaCapture "<bistro|minecraft> <output dir>": the timeline of the research captures c28/c29
//     (Ultra unless noted, fixed 60 Hz, warm-up 60 frames at flythrough play time 2.0, then still 60 /
//     move 120 / still 60 frames from 2.0 to 4.0, history reset at frame 0, 1920x1061 window) for SMAA 1X
//     at the four presets (O-1X = Ultra, O-High, O-Medium, O-Low) and SMAA Adaptive + Temporal at the four
//     presets (AT-Ultra, AT-High, AT-Medium, AT-Low). One RGB PNG of the final colour per frame.
//   -improvedSmaaShowcase "<bistro|minecraft> <output dir>": UI shown, SMAA Adaptive + Temporal (then
//     SMAA 1X for comparison) at Ultra while the flythrough moves from play time 2.0 at normal speed. Saves
//     the displayed back buffer with the UI and the final colour at frames 0, 60, 120, 180 and 239.
class BenchItemImprovedSmaaValidation : public AutoBenchToolWorkItem {
    struct Mode {const char *name; CMAA2Sample::AAType aa; int preset;};
    std::vector<Mode> m_modes;
    bool m_showcase,m_minecraft,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60;
    double m_lastProgress=0;
    std::wstring m_output;
    const Mode& Current() const {return m_modes[m_slot];}
    static bool Saved(int frame) {return frame==0||frame==60||frame==120||frame==180||frame==239;}
    void Configure() {
        const auto& c=Current();auto s=m_parent.GetSMAA();
        s->CleanupTemporaryResources();
        s->GetSettings().Preset=(vaSMAAWrapper::Preset)c.preset;
        m_parent.Settings().CurrentAAOption=c.aa;
        s->ResetTemporalHistory();m_frame=-60;m_rendered=false;
        m_lastProgress=m_parent.GetApplication().GetTimeFromStart();
    }
    void Finish(AutoBenchTool& tool) {
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
        m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemImprovedSmaaValidation(CMAA2Sample& parent,bool showcase,bool minecraft,std::wstring output):
        AutoBenchToolWorkItem(parent),m_showcase(showcase),m_minecraft(minecraft),m_output(output) {
        using AA=CMAA2Sample::AAType;
        if(showcase) {
            m_modes={{"AT-Ultra",AA::SMAA_AdaptiveTemporal,vaSMAAWrapper::PRESET_ULTRA},{"O-1X",AA::SMAA,vaSMAAWrapper::PRESET_ULTRA}};
            return;
        }
        m_modes={{"O-1X",AA::SMAA,vaSMAAWrapper::PRESET_ULTRA},{"O-High",AA::SMAA,vaSMAAWrapper::PRESET_HIGH},
                 {"O-Medium",AA::SMAA,vaSMAAWrapper::PRESET_MEDIUM},{"O-Low",AA::SMAA,vaSMAAWrapper::PRESET_LOW},
                 {"AT-Ultra",AA::SMAA_AdaptiveTemporal,vaSMAAWrapper::PRESET_ULTRA},{"AT-High",AA::SMAA_AdaptiveTemporal,vaSMAAWrapper::PRESET_HIGH},
                 {"AT-Medium",AA::SMAA_AdaptiveTemporal,vaSMAAWrapper::PRESET_MEDIUM},{"AT-Low",AA::SMAA_AdaptiveTemporal,vaSMAAWrapper::PRESET_LOW}};
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(m_done)return;
        if(!m_started) {
            m_started=true;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(m_showcase);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();
            tool.ReportAddText(std::string("Improved SMAA demo validation (")+(m_showcase?"showcase":"capture")+"). Scene: "+(m_minecraft?"minecraft":"bistro")+"\r\n");
            tool.ReportAddText(m_showcase?"UI shown; flythrough from play time 2.0 at normal speed after 60 warm-up frames; back buffer with UI and final colour at frames 0/60/120/180/239.\r\n"
                :"fixed60; warm-up 60 at play time 2.0; still60/move120/still60 from 2.0 to 4.0; history reset at frame 0; one PNG per frame.\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            m_output+=std::wstring(m_showcase?L"/showcase/":L"/capture/")+std::wstring(m_minecraft?L"minecraft/":L"bistro/")+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            Configure();
        }else {
            if(!m_rendered){if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
            m_rendered=false;m_lastProgress=now;
            ++m_frame;
            if(m_frame>=240) {
                if(++m_slot==int(m_modes.size())){Finish(tool);return;}
                Configure();
            }
        }
        const int phase=m_frame<0?0:m_frame%240;
        if(m_frame>=0&&phase==0)m_parent.GetSMAA()->ResetTemporalHistory();
        const float playTime=m_showcase?2.0f+float(phase)/60.0f:2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f;
        m_parent.GetFlythroughCameraController()->SetPlayTime(playTime);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;const auto s=m_parent.GetSMAA();const auto& c=Current();
        const bool improved=c.aa==CMAA2Sample::AAType::SMAA_AdaptiveTemporal;
        bool ok=m_parent.Settings().CurrentAAOption==c.aa&&s->GetSettings().Preset==c.preset
            &&s->GetAdaptiveSearch()==improved&&s->GetSelectedTemporal()==improved&&((s->GetPresentedOutputOverride()!=nullptr)==improved);
        if(color->GetSizeX()!=1920||color->GetSizeY()!=1061){ok=false;tool.ReportAddRowValues({"failed_size",c.name,std::to_string(m_frame),std::to_string(color->GetSizeX()),std::to_string(color->GetSizeY()),"FAIL"});}
        if(!ok)tool.ReportAddRowValues({"failed_state",c.name,std::to_string(m_frame),"FAIL"});
        m_failed=m_failed||!ok;
        if(m_frame<0||(m_showcase&&!Saved(m_frame)))return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),ok?"PASS":"FAIL"});
        const auto dir=m_output+vaStringTools::SimpleWiden(c.name)+L"/";vaFileTools::EnsureDirectoryExists(dir);
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame))))m_failed=true;
        if(m_showcase)m_parent.SaveBackbufferAfterUI(dir+vaStringTools::SimpleWiden(vaStringTools::Format("screen_%05d.png",m_frame)));
    }
    bool IsDone(AutoBenchTool&) const override {return m_done;}
    float GetProgress() const override {return float(m_slot)/float(m_modes.size());}
};

static void QueueImprovedSmaaValidation(CMAA2Sample& parent,AutoBenchTool& tool) {
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()) {
        const bool capture=_wcsicmp(p.first.c_str(),L"improvedSmaaCapture")==0,showcase=_wcsicmp(p.first.c_str(),L"improvedSmaaShowcase")==0;
        if(!capture&&!showcase)continue;
        std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;
        if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and output path without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemImprovedSmaaValidation>(parent,showcase,scene==L"minecraft",output));return;
    }
}
