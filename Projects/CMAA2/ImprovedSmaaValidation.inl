// Validation harness for experiment/improved-smaa-demo-temporal-toggle (validation/improved-smaa-demo-temporal-toggle only).
//   -improvedSmaaCapture "<bistro|minecraft> <output dir>": the timeline of the research captures c28/c29
//     (fixed 60 Hz, warm-up 60 frames at flythrough play time 2.0, then still 60 / move 120 / still 60 frames
//     from 2.0 to 4.0, history reset at frame 0, 1920x1061 window). One RGB PNG of the final colour per frame.
//     Modes: SMAA 1X at the four presets (O-1X = Ultra, O-High, O-Medium, O-Low); SMAA Adaptive + Temporal with
//     the Temporal checkbox On (AT-Ultra, AT-High, AT-Medium, AT-Low) and Off (ATOff-Ultra ... ATOff-Low);
//     AT-Toggle at Ultra, which turns the checkbox Off at frame 90 and On again at frame 150; AT-Reset150 at
//     Ultra, which keeps it On and restarts the history at frame 150.
//   -improvedSmaaShowcase "<bistro|minecraft> <output dir>": UI shown, SMAA Adaptive + Temporal (then
//     SMAA 1X for comparison) at Ultra while the flythrough moves from play time 2.0 at normal speed. Saves
//     the displayed back buffer with the UI and the final colour at frames 0, 60, 120, 180 and 239.
class BenchItemImprovedSmaaValidation : public AutoBenchToolWorkItem {
    enum Temporal {Off,On,Toggle,Reset150};
    struct Mode {const char *name; CMAA2Sample::AAType aa; int preset; Temporal temporal;};
    std::vector<Mode> m_modes;
    bool m_showcase,m_minecraft,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60;
    double m_lastProgress=0;
    std::wstring m_output;
    const Mode& Current() const {return m_modes[m_slot];}
    static bool Saved(int frame) {return frame==0||frame==60||frame==120||frame==180||frame==239;}
    // The Temporal checkbox for a frame of the current mode (warm-up frames are negative).
    bool TemporalAt(int frame) const {const Temporal t=Current().temporal;return t==Off?false:(t==Toggle?!(frame>=90&&frame<150):true);}
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
        const AA AT=AA::SMAA_AdaptiveTemporal;
        const int U=vaSMAAWrapper::PRESET_ULTRA,H=vaSMAAWrapper::PRESET_HIGH,M=vaSMAAWrapper::PRESET_MEDIUM,L=vaSMAAWrapper::PRESET_LOW;
        if(showcase) {
            m_modes={{"AT-Ultra",AT,U,On},{"O-1X",AA::SMAA,U,On}};
            return;
        }
        m_modes={{"O-1X",AA::SMAA,U,On},{"O-High",AA::SMAA,H,On},{"O-Medium",AA::SMAA,M,On},{"O-Low",AA::SMAA,L,On},
                 {"AT-Ultra",AT,U,On},{"AT-High",AT,H,On},{"AT-Medium",AT,M,On},{"AT-Low",AT,L,On},
                 {"ATOff-Ultra",AT,U,Off},{"ATOff-High",AT,H,Off},{"ATOff-Medium",AT,M,Off},{"ATOff-Low",AT,L,Off},
                 {"AT-Toggle",AT,U,Toggle},{"AT-Reset150",AT,U,Reset150}};
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
            tool.ReportAddText(std::string("Improved SMAA demo temporal toggle validation (")+(m_showcase?"showcase":"capture")+"). Scene: "+(m_minecraft?"minecraft":"bistro")+"\r\n");
            tool.ReportAddText(m_showcase?"UI shown; flythrough from play time 2.0 at normal speed after 60 warm-up frames; back buffer with UI and final colour at frames 0/60/120/180/239.\r\n"
                :"fixed60; warm-up 60 at play time 2.0; still60/move120/still60 from 2.0 to 4.0; history reset at frame 0; one PNG per frame. AT-Toggle: Temporal Off at 90, On at 150. AT-Reset150: history reset at 150.\r\n");
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
        auto s=m_parent.GetSMAA();
        if(m_frame>=0&&phase==0)s->ResetTemporalHistory();
        if(Current().temporal==Reset150&&m_frame==150)s->ResetTemporalHistory();
        // What the Temporal checkbox writes; RenderTick passes it on through SetSelectedTemporal.
        s->SetTemporalEnabled(TemporalAt(m_frame));
        const float playTime=m_showcase?2.0f+float(phase)/60.0f:2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f;
        m_parent.GetFlythroughCameraController()->SetPlayTime(playTime);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;const auto s=m_parent.GetSMAA();const auto& c=Current();
        const bool improved=c.aa==CMAA2Sample::AAType::SMAA_AdaptiveTemporal,temporal=improved&&TemporalAt(m_frame);
        // Off must leave no temporal textures and no presented history (and so no velocity pass).
        bool ok=m_parent.Settings().CurrentAAOption==c.aa&&s->GetSettings().Preset==c.preset&&s->GetAdaptiveSearch()==improved
            &&s->GetTemporalEnabled()==TemporalAt(m_frame)&&s->GetSelectedTemporal()==temporal
            &&((s->GetPresentedOutputOverride()!=nullptr)==temporal)&&s->HasTemporalResources()==temporal;
        if(color->GetSizeX()!=1920||color->GetSizeY()!=1061){ok=false;tool.ReportAddRowValues({"failed_size",c.name,std::to_string(m_frame),std::to_string(color->GetSizeX()),std::to_string(color->GetSizeY()),"FAIL"});}
        if(!ok)tool.ReportAddRowValues({"failed_state",c.name,std::to_string(m_frame),"FAIL"});
        m_failed=m_failed||!ok;
        if((c.temporal==Toggle||c.temporal==Reset150)&&(m_frame==89||m_frame==90||m_frame==149||m_frame==150||m_frame==151))
            tool.ReportAddRowValues({"switch_state",c.name,std::to_string(m_frame),std::string("temporal=")+(s->GetTemporalEnabled()?"1":"0"),
                std::string("selected=")+(s->GetSelectedTemporal()?"1":"0"),std::string("resources=")+(s->HasTemporalResources()?"1":"0"),
                std::string("presented=")+(s->GetPresentedOutputOverride()!=nullptr?"1":"0"),ok?"PASS":"FAIL"});
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

// Both modes run without AutoBench, so the UI shows the normal AA option list.
// -improvedSmaaScreens "<bistro|minecraft> <output dir>": at startup it selects SMAA Adaptive + Temporal at Ultra
//   (as clicking the list entry does) and turns on Play animation, then saves the displayed back buffer (with the UI)
//   after 300, 330 and 360 completely drawn frames and quits after 400.
// -improvedSmaaKeys "<bistro|minecraft> <output dir>": Ultra, Play animation and the UI on, the AA option as stored
//   in the settings (the runner stores None). keys.log gets "ready" and the state after 200 completely drawn frames
//   (screen_0.png), then a line for every change of the AA option, the Temporal checkbox, the selected route, the
//   temporal textures, the presented history and the UI visibility. The runner presses the real keys T, Y, F1, Y,
//   F1, waiting for a screen each time; 30 frames after the last change the back buffer is saved (screen_1.png ...).
//   It quits 10 frames after screen_5.png, or after 30000 frames.
void CMAA2Sample::ImprovedSmaaScreensTick(bool lastFrameComplete) {
    static int state=-1,completeFrames=0,lastChange=-1,lastSave=-1,saved=0;static bool keys=false;static std::wstring dir;static std::string lastState;
    if(state==-1) {
        state=-2;
        for(const auto& p:GetApplication().GetCommandLineParameters()) {
            const bool screens=_wcsicmp(p.first.c_str(),L"improvedSmaaScreens")==0;
            keys=_wcsicmp(p.first.c_str(),L"improvedSmaaKeys")==0;
            if(!screens&&!keys)continue;
            std::wistringstream input(p.second);std::wstring scene;input>>scene>>dir;
            if((scene!=L"bistro"&&scene!=L"minecraft")||dir.empty()){VA_LOG_ERROR("Expected scene and output path without spaces");break;}
            m_settings.SceneChoice=scene==L"minecraft"?SceneSelectionType::MinecraftLostEmpire:SceneSelectionType::LumberyardBistro;
            if(screens)m_settings.CurrentAAOption=AAType::SMAA_AdaptiveTemporal;
            m_SMAA->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_flythroughPlay=true;vaUIManager::GetInstance().SetVisible(true);
            vaFileTools::EnsureDirectoryExists(dir+L"/");state=0;break;
        }
    }
    if(state<0||!lastFrameComplete)return;
    ++completeFrames;
    auto& app=const_cast<vaApplicationBase&>(GetApplication());
    if(!keys) {
        if(completeFrames==300||completeFrames==330||completeFrames==360)
            SaveBackbufferAfterUI(dir+L"/"+vaStringTools::SimpleWiden(vaStringTools::Format("screen_%03d.png",completeFrames)));
        if(completeFrames==400)app.Quit();
        return;
    }
    auto log=[&](const std::string& line){FILE* f=nullptr;if(_wfopen_s(&f,(dir+L"/keys.log").c_str(),L"ab")==0&&f){fprintf(f,"%s\r\n",line.c_str());fclose(f);}};
    const std::string now=vaStringTools::Format("aa=%s temporal=%d selected=%d resources=%d presented=%d ui=%d",GetAAName(m_settings.CurrentAAOption),
        m_SMAA->GetTemporalEnabled()?1:0,m_SMAA->GetSelectedTemporal()?1:0,m_SMAA->HasTemporalResources()?1:0,m_SMAA->GetPresentedOutputOverride()!=nullptr?1:0,
        vaUIManager::GetInstance().IsVisible()?1:0);
    if(completeFrames<200)return;
    if(completeFrames==200) {
        lastState=now;log("ready");log(vaStringTools::Format("screen 0 frame %d %s",completeFrames,now.c_str()));
        SaveBackbufferAfterUI(dir+L"/screen_0.png");
    }else if(now!=lastState) {
        lastState=now;lastChange=completeFrames;log(vaStringTools::Format("change frame %d %s",completeFrames,now.c_str()));
    }
    if(lastChange>0&&completeFrames==lastChange+30) {
        ++saved;lastSave=completeFrames;log(vaStringTools::Format("screen %d frame %d %s",saved,completeFrames,now.c_str()));
        SaveBackbufferAfterUI(dir+L"/"+vaStringTools::SimpleWiden(vaStringTools::Format("screen_%d.png",saved)));
    }
    if((saved==5&&completeFrames==lastSave+10)||completeFrames==30000) {
        log(saved==5?"done":"timeout");app.Quit();
    }
}
