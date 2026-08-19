///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Copyright (c) 2019, Intel Corporation
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
// the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
// THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
// TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
// SOFTWARE.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//
// Author(s):  Filip Strugar (filip.strugar@intel.com)
//
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include "CMAA2Sample.h"

#include "Core/System/vaFileTools.h"
#include "Core/Misc/vaProfiler.h"
#include "Rendering/vaShader.h"
#include "Rendering/DirectX/vaRenderDeviceDX11.h"
#include "Rendering/DirectX/vaRenderDeviceDX12.h"
#include "Rendering/vaAssetPack.h"

#include "IntegratedExternals/vaImguiIntegration.h"

#include <iomanip>
#include <sstream> // stringstream
#include <chrono>
#include <thread>
#include <cstring>

using namespace VertexAsylum;

namespace
{
    bool IsSMAASingleSample( CMAA2Sample::AAType aaType )
    {
        return aaType == CMAA2Sample::AAType::SMAA
            || aaType == CMAA2Sample::AAType::SMAA_O_T2X
            || aaType == CMAA2Sample::AAType::SMAA_O_T2X_R
            || aaType == CMAA2Sample::AAType::SMAA_O_ET2X
            || aaType == CMAA2Sample::AAType::SMAA_O_ET2X_R
            || aaType == CMAA2Sample::AAType::SMAA_A_T2X
            || aaType == CMAA2Sample::AAType::SMAA_A_T2X_R
            || aaType == CMAA2Sample::AAType::SMAA_A_ET2X
            || aaType == CMAA2Sample::AAType::SMAA_A_ET2X_R
            || aaType == CMAA2Sample::AAType::SMAA_A_1X
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER
            || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER;
    }

    vaSMAAWrapper::SpatialSearch GetSMAASpatialSearchForAAType( CMAA2Sample::AAType aaType )
    {
        switch( aaType )
        {
        case CMAA2Sample::AAType::SMAA_A_T2X:
        case CMAA2Sample::AAType::SMAA_A_T2X_R:
        case CMAA2Sample::AAType::SMAA_A_ET2X:
        case CMAA2Sample::AAType::SMAA_A_ET2X_R:
        case CMAA2Sample::AAType::SMAA_A_1X:
            return vaSMAAWrapper::SpatialSearch::AdaptiveContrast;
        default:
            return vaSMAAWrapper::SpatialSearch::Original;
        }
    }

    vaSMAAWrapper::TemporalSettings GetSMAATemporalSettingsForAAType( CMAA2Sample::AAType aaType )
    {
        vaSMAAWrapper::TemporalSettings settings;

        switch( aaType )
        {
        case CMAA2Sample::AAType::SMAA_O_T2X:
        case CMAA2Sample::AAType::SMAA_A_T2X:
            settings.Coverage = vaSMAAWrapper::TemporalCoverage::FullScreen;
            settings.Reprojection = vaSMAAWrapper::ReprojectionMode::Off;
            settings.Jitter = vaSMAAWrapper::JitterPolicy::SMAAT2X;
            settings.Sampler = vaSMAAWrapper::HistorySampler::Bilinear;
            settings.Clipping = vaSMAAWrapper::HistoryClipping::Off;
            settings.HistoryWeight = 0.5f;
            break;
        case CMAA2Sample::AAType::SMAA_O_T2X_R:
        case CMAA2Sample::AAType::SMAA_A_T2X_R:
            settings.Coverage = vaSMAAWrapper::TemporalCoverage::FullScreen;
            settings.Reprojection = vaSMAAWrapper::ReprojectionMode::CameraDepthMatrices;
            settings.Jitter = vaSMAAWrapper::JitterPolicy::SMAAT2X;
            settings.Sampler = vaSMAAWrapper::HistorySampler::Bilinear;
            settings.Clipping = vaSMAAWrapper::HistoryClipping::Off;
            settings.HistoryWeight = 0.5f;
            break;
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER:
            // Controlled ablation against O-T2X-R: preserve reprojection,
            // deliberate T2X jitter and the Intel-family candidate policy,
            // then cumulatively enable one document-profile component at a
            // time so every adjacent profile has exactly one changed factor.
            settings.Coverage = vaSMAAWrapper::TemporalCoverage::EdgeSelective;
            settings.Reprojection = vaSMAAWrapper::ReprojectionMode::CameraDepthMatrices;
            settings.Jitter =
                aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER?
                vaSMAAWrapper::JitterPolicy::None :
                vaSMAAWrapper::JitterPolicy::SMAAT2X;
            settings.Candidates = vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant;
            settings.NonDominantRemovalAmount = 0.5f;
            settings.Sampler =
                (aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R
                    || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER
                    || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3
                    || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER)?
                vaSMAAWrapper::HistorySampler::Bilinear :
                vaSMAAWrapper::HistorySampler::CatmullRom5Tap;
            settings.Clipping =
                (aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R
                    || aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R)?
                vaSMAAWrapper::HistoryClipping::YCoCgVariance :
                vaSMAAWrapper::HistoryClipping::Off;
            settings.NonCandidate =
                aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE?
                vaSMAAWrapper::NonCandidateBase::DeJitteredSpatial :
                vaSMAAWrapper::NonCandidateBase::CurrentSpatial;
            settings.Expansion = vaSMAAWrapper::CandidateExpansion::None;
            if( aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3 )
                settings.Expansion = vaSMAAWrapper::CandidateExpansion::Dilate3x3;
            else if( aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER )
                settings.Expansion = vaSMAAWrapper::CandidateExpansion::FilteredQuarter;
            settings.HistoryWeight =
                aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R?
                0.8f : 0.5f;
            break;
        case CMAA2Sample::AAType::SMAA_O_ET2X:
        case CMAA2Sample::AAType::SMAA_O_ET2X_R:
        case CMAA2Sample::AAType::SMAA_A_ET2X:
        case CMAA2Sample::AAType::SMAA_A_ET2X_R:
            settings.Coverage = vaSMAAWrapper::TemporalCoverage::EdgeSelective;
            settings.Reprojection = (aaType == CMAA2Sample::AAType::SMAA_O_ET2X_R
                || aaType == CMAA2Sample::AAType::SMAA_A_ET2X_R)?
                vaSMAAWrapper::ReprojectionMode::CameraDepthMatrices : vaSMAAWrapper::ReprojectionMode::Off;
            settings.Jitter = vaSMAAWrapper::JitterPolicy::None;
            // Intel-document-family SMAA adaptation. The exact candidate,
            // Catmull-Rom and clipping equations remain documented adaptation
            // choices and independently selectable diagnostic overrides.
            settings.Sampler = vaSMAAWrapper::HistorySampler::CatmullRom5Tap;
            settings.Clipping = vaSMAAWrapper::HistoryClipping::YCoCgVariance;
            settings.Candidates = vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant;
            settings.HistoryWeight = 0.8f;
            settings.NonDominantRemovalAmount = 0.5f;
            break;
        case CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3:
        case CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER:
            settings.Coverage = vaSMAAWrapper::TemporalCoverage::EdgeSelective;
            settings.Reprojection = vaSMAAWrapper::ReprojectionMode::CameraDepthMatrices;
            settings.Jitter = vaSMAAWrapper::JitterPolicy::None;
            settings.Sampler = vaSMAAWrapper::HistorySampler::CatmullRom5Tap;
            settings.Clipping = vaSMAAWrapper::HistoryClipping::YCoCgVariance;
            settings.Candidates = vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant;
            settings.Expansion =
                aaType == CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3?
                vaSMAAWrapper::CandidateExpansion::Dilate3x3 :
                vaSMAAWrapper::CandidateExpansion::FilteredQuarter;
            settings.HistoryWeight = 0.8f;
            settings.NonDominantRemovalAmount = 0.5f;
            break;
        default:
            break;
        }

        return settings;
    }

    const char * GetTemporalCoverageName( vaSMAAWrapper::TemporalCoverage value )
    {
        switch( value )
        {
        case vaSMAAWrapper::TemporalCoverage::Disabled:      return "Disabled";
        case vaSMAAWrapper::TemporalCoverage::FullScreen:    return "FullScreen";
        case vaSMAAWrapper::TemporalCoverage::EdgeSelective: return "EdgeSelective";
        default:                                             return "Unknown";
        }
    }

    const char * GetSpatialSearchName( vaSMAAWrapper::SpatialSearch value )
    {
        return value == vaSMAAWrapper::SpatialSearch::AdaptiveContrast? "AdaptiveContrast" : "Original";
    }

    const char * GetReprojectionModeName( vaSMAAWrapper::ReprojectionMode value )
    {
        return (value == vaSMAAWrapper::ReprojectionMode::CameraDepthMatrices)? "CameraDepthMatrices" : "Off";
    }

    const char * GetJitterPolicyName( vaSMAAWrapper::JitterPolicy value )
    {
        return (value == vaSMAAWrapper::JitterPolicy::SMAAT2X)? "SMAAT2X" : "None";
    }

    const char * GetHistorySamplerName( vaSMAAWrapper::HistorySampler value )
    {
        return (value == vaSMAAWrapper::HistorySampler::CatmullRom5Tap)? "CatmullRom5Tap" : "Bilinear";
    }

    const char * GetHistoryClippingName( vaSMAAWrapper::HistoryClipping value )
    {
        return (value == vaSMAAWrapper::HistoryClipping::YCoCgVariance)? "YCoCgVariance" : "Off";
    }

    const char * GetNonCandidateBaseName( vaSMAAWrapper::NonCandidateBase value )
    {
        return value == vaSMAAWrapper::NonCandidateBase::DeJitteredSpatial?
            "DeJitteredSpatial" : "CurrentSpatial";
    }

    const char * GetCandidatePolicyName( vaSMAAWrapper::CandidatePolicy value )
    {
        switch( value )
        {
        case vaSMAAWrapper::CandidatePolicy::AllBaseEdges:                       return "AllBaseEdges";
        case vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant:             return "IntelFamilyNonDominant";
        case vaSMAAWrapper::CandidatePolicy::ExperimentalLocalMeanMax3x3:        return "ExperimentalLocalMeanMax3x3";
        default:                                                                 return "Unknown";
        }
    }

    const char * GetCandidateExpansionName( vaSMAAWrapper::CandidateExpansion value )
    {
        switch( value )
        {
        case vaSMAAWrapper::CandidateExpansion::None:            return "None";
        case vaSMAAWrapper::CandidateExpansion::Dilate3x3:       return "Dilate3x3";
        case vaSMAAWrapper::CandidateExpansion::FilteredQuarter: return "FilteredQuarter";
        default:                                                  return "Unknown";
        }
    }

    bool TryParseSMAACameraMotionScene(
        const wstring & token, CMAA2Sample::SceneSelectionType & scene )
    {
        if( _wcsicmp( token.c_str( ), L"bistro" ) == 0 )
            scene = CMAA2Sample::SceneSelectionType::LumberyardBistro;
        else if( _wcsicmp( token.c_str( ), L"minecraft" ) == 0 )
            scene = CMAA2Sample::SceneSelectionType::MinecraftLostEmpire;
        else if( _wcsicmp( token.c_str( ), L"powerplant" ) == 0 )
            scene = CMAA2Sample::SceneSelectionType::PowerPlantThinGeometry;
        else if( _wcsicmp( token.c_str( ), L"sanmiguel" ) == 0 )
            scene = CMAA2Sample::SceneSelectionType::SanMiguelTextured;
        else
            return false;
        return true;
    }

    bool TryParseSMAACameraMotionProfile(
        const wstring & token, CMAA2Sample::SMAACameraMotionProfile & profile )
    {
        if( _wcsicmp( token.c_str( ), L"yaw-slow-360" ) == 0 )
            profile = CMAA2Sample::SMAACameraMotionProfile::YawSlow360;
        else if( _wcsicmp( token.c_str( ), L"yaw-fast-360" ) == 0 )
            profile = CMAA2Sample::SMAACameraMotionProfile::YawFast360;
        else if( _wcsicmp( token.c_str( ), L"yaw-extreme-360" ) == 0 )
            profile = CMAA2Sample::SMAACameraMotionProfile::YawExtreme360;
        else if( _wcsicmp( token.c_str( ), L"strafe-fast" ) == 0 )
            profile = CMAA2Sample::SMAACameraMotionProfile::StrafeFast;
        else if( _wcsicmp( token.c_str( ), L"yaw-strafe-fast" ) == 0 )
            profile = CMAA2Sample::SMAACameraMotionProfile::YawStrafeFast;
        else
            return false;
        return true;
    }

    bool TryParseSMAAResearchMode(
        const wstring & token, CMAA2Sample::AAType & mode, string & semanticID )
    {
        struct ModeEntry
        {
            const wchar_t * Token;
            CMAA2Sample::AAType Mode;
            const char * SemanticID;
        };
        static const ModeEntry c_modes[] =
        {
            { L"O-1X",     CMAA2Sample::AAType::SMAA,          "O-1X" },
            { L"O-T2X",    CMAA2Sample::AAType::SMAA_O_T2X,    "O-T2X" },
            { L"O-T2X-R",  CMAA2Sample::AAType::SMAA_O_T2X_R,  "O-T2X-R" },
            { L"O-ET2X",   CMAA2Sample::AAType::SMAA_O_ET2X,   "O-ET2X" },
            { L"O-ET2X-R", CMAA2Sample::AAType::SMAA_O_ET2X_R, "O-ET2X-R" },
            { L"A-1X",     CMAA2Sample::AAType::SMAA_A_1X,     "A-1X" },
            { L"A-T2X",    CMAA2Sample::AAType::SMAA_A_T2X,    "A-T2X" },
            { L"A-T2X-R",  CMAA2Sample::AAType::SMAA_A_T2X_R,  "A-T2X-R" },
            { L"A-ET2X",   CMAA2Sample::AAType::SMAA_A_ET2X,   "A-ET2X" },
            { L"A-ET2X-R", CMAA2Sample::AAType::SMAA_A_ET2X_R, "A-ET2X-R" },
        };
        for( const ModeEntry & entry : c_modes )
        {
            if( _wcsicmp( token.c_str( ), entry.Token ) == 0 )
            {
                mode = entry.Mode;
                semanticID = entry.SemanticID;
                return true;
            }
        }
        return false;
    }
}

void CMAA2StartStopCallback(vaApplicationBase& application, bool starting)
{
    static shared_ptr<CMAA2Sample> cmaa2Sample;

    if (starting)
    {
        cmaa2Sample = VA_RENDERING_MODULE_CREATE_SHARED(CMAA2Sample, CMAA2SampleConstructorParams(application.GetRenderDevice(), application));
        application.Event_Tick.Add(cmaa2Sample, &CMAA2Sample::OnTick);
        application.Event_BeforeStopped.Add(cmaa2Sample, &CMAA2Sample::OnBeforeStopped);
        application.Event_SerializeSettings.Add(cmaa2Sample, &CMAA2Sample::OnSerializeSettings);
    }
    else
    {
        cmaa2Sample = nullptr;
    }
}

int APIENTRY _tWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPTSTR lpCmdLine, int nCmdShow)
{
    hInstance; hPrevInstance; // unreferenced

    {
        vaCoreInitDeinit core;
        vaApplicationWin::Settings settings(L"CMAA2 DX11/DX12 sample", lpCmdLine, nCmdShow);
#ifdef _DEBUG
        settings.Vsync = false;
#else
        settings.Vsync = false;
#endif

        void InitializeProjectAPIParts();
        InitializeProjectAPIParts();

        vaApplicationWin::Run(settings, CMAA2StartStopCallback);
    }
    return 0;
}


static wstring CameraFileName(int index)
{
    wstring fileName = vaCore::GetExecutableDirectory() + L"last";
    if (index != -1)
        fileName += vaStringTools::Format(L"_%d", index);
    fileName += L".camerastate";
    return fileName;
}

CMAA2Sample::CMAA2Sample(const vaRenderingModuleParams& params) : vaRenderingModule(params), m_autoBench(std::make_shared<AutoBenchTool>(*this)),
m_application(vaSaferStaticCast< const CMAA2SampleConstructorParams&, const vaRenderingModuleParams&>(params).Application),
vaUIPanel(vaStringTools::SimpleNarrow(vaSaferStaticCast< const CMAA2SampleConstructorParams&, const vaRenderingModuleParams&>(params).Application.GetSettings().AppName), 0, true, vaUIPanel::DockLocation::DockedLeft, "", vaVector2(500, 750))
{
    m_camera = std::shared_ptr<vaCameraBase>(new vaCameraBase(true));

    m_camera->SetPosition(vaVector3(4.3f, 29.2f, 14.2f));
    m_camera->SetOrientationLookAt(vaVector3(6.5f, 0.0f, 8.7f));

    m_cameraFreeFlightController = std::shared_ptr<vaCameraControllerFreeFlight>(new vaCameraControllerFreeFlight());
    m_cameraFreeFlightController->SetMoveWhileNotCaptured(false);

    m_flythroughCameraController = std::make_shared<vaCameraControllerFlythrough>();
    const float keyTimeStep = 8.0f;
    float keyTime = 0.0f;
    // search for HACKY_FLYTHROUGH_RECORDER on how to 'record' these if need be 
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(-15.027f, -3.197f, 2.179f), vaQuaternion(0.480f, 0.519f, 0.519f, 0.480f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(-8.101f, 2.689f, 1.289f), vaQuaternion(0.564f, 0.427f, 0.427f, 0.564f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(-4.239f, 4.076f, 1.621f), vaQuaternion(0.626f, 0.329f, 0.329f, 0.626f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(2.922f, 5.273f, 1.520f), vaQuaternion(0.660f, 0.255f, 0.255f, 0.660f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(6.134f, 5.170f, 1.328f), vaQuaternion(0.680f, 0.195f, 0.195f, 0.680f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(7.658f, 4.902f, 1.616f), vaQuaternion(0.703f, 0.078f, 0.078f, 0.703f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(8.318f, 3.589f, 2.072f), vaQuaternion(0.886f, -0.331f, -0.114f, 0.304f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(8.396f, 3.647f, 2.072f), vaQuaternion(0.615f, 0.262f, 0.291f, 0.684f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(9.750f, 0.866f, 2.131f), vaQuaternion(0.747f, -0.131f, -0.113f, 0.642f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(11.496f, -0.826f, 2.429f), vaQuaternion(0.602f, -0.510f, -0.397f, 0.468f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(10.943f, -1.467f, 2.883f), vaQuaternion(0.704f, 0.183f, 0.173f, 0.664f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(7.312f, -3.135f, 2.869f), vaQuaternion(0.692f, 0.159f, 0.158f, 0.686f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(7.559f, -3.795f, 2.027f), vaQuaternion(0.695f, 0.116f, 0.117f, 0.700f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(6.359f, -4.580f, 1.856f), vaQuaternion(0.749f, -0.320f, -0.228f, 0.533f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(5.105f, -6.682f, 0.937f), vaQuaternion(0.559f, -0.421f, -0.429f, 0.570f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(3.612f, -5.566f, 1.724f), vaQuaternion(0.771f, -0.024f, -0.020f, 0.636f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(2.977f, -5.532f, 1.757f), vaQuaternion(0.698f, -0.313f, -0.263f, 0.587f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(1.206f, -1.865f, 1.757f), vaQuaternion(0.701f, -0.204f, -0.191f, 0.657f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(0.105f, -1.202f, 1.969f), vaQuaternion(0.539f, 0.558f, 0.453f, 0.439f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(-6.314f, -1.144f, 1.417f), vaQuaternion(0.385f, 0.672f, 0.549f, 0.314f), keyTime)); keyTime += keyTimeStep;
    m_flythroughCameraController->AddKey(vaCameraControllerFlythrough::Keyframe(vaVector3(-15.027f, -3.197f, 2.179f), vaQuaternion(0.480f, 0.519f, 0.519f, 0.480f), keyTime + 0.01f)); keyTime += keyTimeStep;
    m_flythroughCameraController->SetFixedUp(true);

    m_skybox = VA_RENDERING_MODULE_CREATE_SHARED(vaSkybox, GetRenderDevice());
    m_GBuffer = VA_RENDERING_MODULE_CREATE_SHARED(vaGBuffer, GetRenderDevice());
    m_lighting = VA_RENDERING_MODULE_CREATE_SHARED(vaLighting, GetRenderDevice());
    m_postProcess = VA_RENDERING_MODULE_CREATE_SHARED(vaPostProcess, GetRenderDevice());
    m_postProcessTonemap = VA_RENDERING_MODULE_CREATE_SHARED(vaPostProcessTonemap, GetRenderDevice());

    m_SSAOLiteEffect = std::make_shared<vaASSAOLite>(GetRenderDevice());

    // this is used for all frame buffer needs - color, depth, linear depth, gbuffer material stuff if used, etc.
    m_GBufferFormats = m_GBuffer->GetFormats();

    // disable, unused
    m_GBufferFormats.DepthBufferViewspaceLinear = vaResourceFormat::Unknown;

    // use lower precision for perf reasons - default is R16G16B16A16_FLOAT
    m_GBufferFormats.Radiance = vaResourceFormat::R11G11B10_FLOAT;

#if 0 // for testing the path for HDR displays (not all codepaths will support it - for ex, SMAA requires unconverted sRGB as the input)
    m_GBufferFormats.OutputColorTypeless = vaResourceFormat::R11G11B10_FLOAT;
    m_GBufferFormats.OutputColorView = vaResourceFormat::R11G11B10_FLOAT;
    m_GBufferFormats.OutputColorIgnoreSRGBConvView = vaResourceFormat::R11G11B10_FLOAT;
    m_GBufferFormats.OutputColorR32UINT_UAV = vaResourceFormat::Unknown;
#endif
#if 0 // for testing the path for HDR displays (not all codepaths will support it - for ex, SMAA requires unconverted sRGB as the input)
    m_GBufferFormats.OutputColorTypeless = vaResourceFormat::R16G16B16A16_FLOAT;
    m_GBufferFormats.OutputColorView = vaResourceFormat::R16G16B16A16_FLOAT;
    m_GBufferFormats.OutputColorIgnoreSRGBConvView = vaResourceFormat::R16G16B16A16_FLOAT;
    m_GBufferFormats.OutputColorR32UINT_UAV = vaResourceFormat::Unknown;
#endif

    m_loadedScreenshotFullPath = "";

    auto& tonemapSettings = m_postProcessTonemap->Settings();
    tonemapSettings.UseAutoExposure = true;
    tonemapSettings.Enabled = true;        // for debugging using values it's easier if it's disabled
    tonemapSettings.AutoExposureKeyValue = 0.5f;
    tonemapSettings.ExposureMax = 4.0f;
    tonemapSettings.ExposureMin = -4.0f;
    tonemapSettings.UseBloom = true;
    tonemapSettings.BloomSize = 0.25f;
    tonemapSettings.BloomThreshold = 0.015f;
    tonemapSettings.BloomMultiplier = 0.03f;
    tonemapSettings.AutoExposureAdaptationSpeed = 5.0f; std::numeric_limits<float>::infinity();   // for testing purposes we're setting this to infinity

    if (m_SSAOLiteEffect.get() != nullptr)
    {
        auto& ssaoSettings = m_SSAOLiteEffect->GetSettings();
        ssaoSettings.Radius = 0.5f;
        ssaoSettings.ShadowMultiplier = 0.43f;
        ssaoSettings.ShadowPower = 1.5f;
        ssaoSettings.QualityLevel = 1;
        ssaoSettings.BlurPassCount = 1;
        ssaoSettings.DetailShadowStrength = 2.5f;
#if 0 // drop to low quality for more perf
        ssaoSettings.QualityLevel = 0;
        ssaoSettings.ShadowMultiplier = 0.4f;
#endif
    }

    {
        vaFileStream fileIn;
        if (fileIn.Open(CameraFileName(-1), FileCreationMode::Open))
        {
            m_camera->Load(fileIn);
        }
        else if (fileIn.Open(vaCore::GetExecutableDirectory() + L"default.camerastate", FileCreationMode::Open))
        {
            m_camera->Load(fileIn);
        }
    }
    m_camera->AttachController(m_cameraFreeFlightController);

    m_lastDeltaTime = 0.0f;

    m_CMAA2 = VA_RENDERING_MODULE_CREATE_SHARED(vaCMAA2, GetRenderDevice());

    // dx12 version not supported unfortunately
    //if( dynamic_cast<vaRenderDeviceDX12*>( &GetRenderDevice() ) == nullptr )
    m_SMAA = VA_RENDERING_MODULE_CREATE_SHARED(vaSMAAWrapper, GetRenderDevice());

    m_FXAA = std::make_shared< vaFXAAWrapper >(GetRenderDevice());

    m_zoomTool = std::make_shared<vaZoomTool>(GetRenderDevice());
    m_imageCompareTool = std::make_shared<vaImageCompareTool>(GetRenderDevice());

    // create scene objects
    for (int i = 0; i < _countof(m_scenes); i++)
        m_scenes[i] = std::make_shared<vaScene>();

    m_currentScene = nullptr;

    LoadAssetsAndScenes();
}

CMAA2Sample::~CMAA2Sample()
{
#if 1 || defined( _DEBUG )
    SaveCamera();
#endif
}

const char* CMAA2Sample::GetAAName(AAType aaType)
{
    switch (aaType)
    {
    case CMAA2Sample::AAType::None:                 return "None";
    case CMAA2Sample::AAType::CMAA2:                return "CMAA2";
    case CMAA2Sample::AAType::MSAA2x:               return "2xMSAA";
    case CMAA2Sample::AAType::MSAA4x:               return "4xMSAA";
    case CMAA2Sample::AAType::MSAA8x:               return "8xMSAA";
#if MSAA_16x_SUPPORTED
    case CMAA2Sample::AAType::MSAA16x:              return "16xMSAA";
#endif
    case CMAA2Sample::AAType::MSAA2xPlusCMAA2:      return "2xMSAA+CMAA2";
    case CMAA2Sample::AAType::MSAA4xPlusCMAA2:      return "4xMSAA+CMAA2";
    case CMAA2Sample::AAType::MSAA8xPlusCMAA2:      return "8xMSAA+CMAA2";
    case CMAA2Sample::AAType::SuperSampleReference: return "SuperSampleReference";

    case CMAA2Sample::AAType::SMAA:                 return "Original SMAA 1X";
    case CMAA2Sample::AAType::SMAA_O_T2X:           return "O-T2X - Original SMAA Standard T2X";
    case CMAA2Sample::AAType::SMAA_O_T2X_R:         return "O-T2X-R - Original SMAA Standard T2X + camera reprojection";
    case CMAA2Sample::AAType::SMAA_O_ET2X:          return "O-ET2X - Original SMAA TSCMAA-inspired edge-selective temporal [no-reprojection ablation]";
    case CMAA2Sample::AAType::SMAA_O_ET2X_R:        return "O-ET2X-R - Original SMAA TSCMAA-inspired edge-selective temporal + camera reprojection";
    case CMAA2Sample::AAType::SMAA_A_T2X:           return "A-T2X - Adaptive SMAA Standard T2X";
    case CMAA2Sample::AAType::SMAA_A_T2X_R:         return "A-T2X-R - Adaptive SMAA Standard T2X + camera reprojection";
    case CMAA2Sample::AAType::SMAA_A_ET2X:          return "A-ET2X - Adaptive SMAA TSCMAA-inspired edge-selective temporal [no-reprojection ablation]";
    case CMAA2Sample::AAType::SMAA_A_ET2X_R:        return "A-ET2X-R - Adaptive SMAA TSCMAA-inspired edge-selective temporal + camera reprojection";
    case CMAA2Sample::AAType::SMAA_A_1X:            return "A-1X - Adaptive SMAA spatial-only quality control";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R:
        return "ABL-CandidateOnly-R - O-T2X-R with edge-selective candidates as the only temporal change";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R:
        return "ABL-Candidate+Catmull-R - Candidate-only plus Catmull-Rom 5-tap";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R:
        return "ABL-Candidate+Catmull+Clip-R - Previous ablation plus YCoCg variance clipping";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R:
        return "ABL-Candidate+Catmull+Clip+W0.8-R - Previous ablation plus history weight 0.8";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER:
        return "ABL-CandidateOnly-NoJitter-R - Candidate-only with deliberate projection jitter disabled";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE:
        return "ABL-Candidate-DeJitter-R - Candidate-only jitter path with de-jittered noncandidate spatial base";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3:
        return "ABL-Candidate-Jitter-Dilate3x3-R - Candidate-Jitter plus current-edge 3x3 dilation";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3:
        return "ABL-Document-Dilate3x3-R - O-ET2X-R document profile plus current-edge 3x3 dilation";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER:
        return "ABL-Candidate-Jitter-FilteredQuarter-R - Candidate-Jitter plus filtered 1/4 candidate expansion";
    case CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER:
        return "ABL-Document-FilteredQuarter-R - O-ET2X-R document profile plus filtered 1/4 candidate expansion";
    case CMAA2Sample::AAType::SMAA_S2x:             return "SMAA_S2x";
    case CMAA2Sample::AAType::FXAA:                 return "FXAA";
        //    case CMAA2Sample::AAType::ExperimentalSlot1:    return "Experimental slot 1";   // at the moment tonemap+CMAA2
        //    case CMAA2Sample::AAType::ExperimentalSlot2:    return "Old CMAA";              // return "ColorPostProcess";
    case CMAA2Sample::AAType::MaxValue:
    default:
        assert(false);
        return nullptr;
        break;
    }
}

int CMAA2Sample::GetMSAACountForAAType(CMAA2Sample::AAType aaType)
{
    switch (aaType)
    {
    case CMAA2Sample::AAType::None:
    case CMAA2Sample::AAType::CMAA2:
        return 1;
    case CMAA2Sample::AAType::MSAA2x:               return 2;
    case CMAA2Sample::AAType::MSAA4x:               return 4;
    case CMAA2Sample::AAType::MSAA8x:               return 8;
#if MSAA_16x_SUPPORTED
    case CMAA2Sample::AAType::MSAA16x:              return 16;
#endif
    case CMAA2Sample::AAType::MSAA2xPlusCMAA2:      return 2;
    case CMAA2Sample::AAType::MSAA4xPlusCMAA2:      return 4;
    case CMAA2Sample::AAType::MSAA8xPlusCMAA2:      return 8;
    case CMAA2Sample::AAType::SuperSampleReference: return m_SSMSAASampleCount;
    case CMAA2Sample::AAType::SMAA:                 return 1;
    case CMAA2Sample::AAType::SMAA_O_T2X:           return 1;
    case CMAA2Sample::AAType::SMAA_O_T2X_R:         return 1;
    case CMAA2Sample::AAType::SMAA_O_ET2X:          return 1;
    case CMAA2Sample::AAType::SMAA_O_ET2X_R:        return 1;
    case CMAA2Sample::AAType::SMAA_A_T2X:           return 1;
    case CMAA2Sample::AAType::SMAA_A_T2X_R:         return 1;
    case CMAA2Sample::AAType::SMAA_A_ET2X:          return 1;
    case CMAA2Sample::AAType::SMAA_A_ET2X_R:        return 1;
    case CMAA2Sample::AAType::SMAA_A_1X:            return 1;
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R:
        return 1;
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER:
    case CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER:
        return 1;
    case CMAA2Sample::AAType::SMAA_S2x:             return 2;
    case CMAA2Sample::AAType::FXAA:                 return 1;
        //    case CMAA2Sample::AAType::ExperimentalSlot1:    return 4;   // at the moment use to test 4xMSAA + CMAA but applied after
        //    case CMAA2Sample::AAType::ExperimentalSlot2:    return 1;   // used to test various things
    default:
        assert(false);
        break;
    }
    return -1;
}

bool CMAA2Sample::LoadCamera(int index)
{
    vaFileStream fileIn;
    if (fileIn.Open(CameraFileName(index), FileCreationMode::Open))
    {
        m_camera->Load(fileIn);
        m_camera->AttachController(m_cameraFreeFlightController);
        m_SMAA->ResetTemporalHistory();
        return true;
    }
    return false;
}

void CMAA2Sample::SaveCamera(int index)
{
    vaFileStream fileOut;
    if (fileOut.Open(CameraFileName(index), FileCreationMode::Create))
    {
        m_camera->Save(fileOut);
    }
}

void CMAA2Sample::LoadAssetsAndScenes()
{
    // this loads and initializes asset pack manager - and at the moment loads assets
    GetRenderDevice().GetAssetPackManager().LoadPacks("*", true);  // these should be loaded automatically by scenes that need them but for now just load all in the asset folder

    wstring mediaRootFolder = vaCore::GetExecutableDirectory() + L"Media\\";
    m_screenshotFolder = mediaRootFolder + L"TestScreenshots\\";

    // Manually load skybox texture 
    {
        //vaVector3 ambientLightIntensity( 0.1f, 0.1f, 0.1f );
        //vaVector3 directionaLightIntensity( 1.0f, 1.0f, 0.8f );
        //vaVector3 directionaLightDirection = vaVector3( 0.5f, 0.5f, -1.0f ).Normalized();

        // // shared_ptr<vaTexture> skyboxTexture = vaTexture::CreateFromImageFile( mediaRootFolder + L"sky_cube.dds", vaTextureLoadFlags::Default );
        // for( int i = 0; i < _countof(m_scenes); i++ )
        // {
        //     m_scenes[i]->SetSkybox( GetRenderDevice(), "Media\\sky_cube.dds", vaMatrix3x3::Identity, 3.0f );
        //     m_scenes[i]->Lights().push_back( std::make_shared<vaLight>( vaLight::MakeAmbient( "Ambient", ambientLightIntensity ) ) );
        //     m_scenes[i]->Lights().push_back( std::make_shared<vaLight>( vaLight::MakeDirectional( "Sun", directionaLightIntensity, directionaLightDirection ) ) );
        // }
    }

    // Screenshot scene (empty)
    m_scenes[(int32)SceneSelectionType::StaticImage]->Clear();
    m_scenes[(int32)SceneSelectionType::StaticImage]->Name() = "StaticImage";

    // Load screenshot images
    {
        auto wlist = vaFileTools::FindFiles(m_screenshotFolder, L"*.png", false);
        m_staticImageList.clear();
        for (auto& fullPath : wlist)
        {
            wstring justName, justExt;
            vaFileTools::SplitPath(fullPath, nullptr, &justName, &justExt);
            m_staticImageList.push_back(vaStringTools::SimpleNarrow(justName + justExt));
            m_staticImageFullPaths.push_back(vaStringTools::SimpleNarrow(fullPath));
        }
    }

    // Minecraft scene (not sure why I still have this in but hey it's small and there's lots of alpha tested trees so I guess it could be useful for testing?)
    {
        // // Manually create
        // m_scenes[ (int32)SceneSelectionType::MinecraftLostEmpire ]->Name()  = "MinecraftLostEmpire";
        // InsertAllPackMeshesToSceneAsObjects( *m_scenes[(int32)SceneSelectionType::MinecraftLostEmpire], *assetsMinecraftLostEmpire, vaMatrix4x4::Translation( 0.0f, 0.0f, -20.0f ) );

        // Load from file
        m_scenes[(int32)SceneSelectionType::MinecraftLostEmpire]->Load(mediaRootFolder + L"MinecraftLostEmpire.scene.xml");

        //vaVector3 ambientLightIntensity( 0.1f, 0.1f, 0.1f );
        //vaVector3 directionaLightIntensity( 1.0f, 1.0f, 0.8f );
        //vaVector3 directionaLightDirection = vaVector3( 0.5f, 0.5f, -1.0f ).Normalized();
        m_scenes[(int32)SceneSelectionType::MinecraftLostEmpire]->SetSkybox(GetRenderDevice(), "Media\\sky_cube.dds", vaMatrix3x3::Identity, 3.0f);
        // m_scenes[(int32)SceneSelectionType::MinecraftLostEmpire]->Lights().push_back( std::make_shared<vaLight>( vaLight::MakeAmbient( "Ambient", ambientLightIntensity ) ) );
        // m_scenes[(int32)SceneSelectionType::MinecraftLostEmpire]->Lights().push_back( std::make_shared<vaLight>( vaLight::MakeDirectional( "Sun", directionaLightIntensity, directionaLightDirection ) ) );
    }

    // Bistro scene
    {
        // // Manually create
        // m_scenes[ (int32)SceneSelectionType::MinecraftLostEmpire ]->Name()  = "MinecraftLostEmpire";
        // InsertAllPackMeshesToSceneAsObjects( *m_scenes[(int32)SceneSelectionType::MinecraftLostEmpire], *assetsMinecraftLostEmpire, vaMatrix4x4::Translation( 0.0f, 0.0f, -20.0f ) );

        // Load from file
        m_scenes[(int32)SceneSelectionType::LumberyardBistro]->Name() = "LumberyardBistro";
        m_scenes[(int32)SceneSelectionType::LumberyardBistro]->Load(mediaRootFolder + L"Bistro.scene.xml");

        vaMatrix3x3 mat = vaMatrix3x3::RotationAxis(vaVector3(0, 0, 1), -0.25f * VA_PIf) * vaMatrix3x3::RotationAxis(vaVector3(1, 0, 0), -0.5f * VA_PIf);
        // vaMatrix3x3::RotationAxis( vaVector3( 1, 0, 0 ), -0.5f * VA_PIf ) /** vaMatrix3x3::RotationAxis( vaVector3( 0, 0, 1 ), 1.0f * VA_PIf )*/

        m_scenes[(int32)SceneSelectionType::LumberyardBistro]->SetEnvmap(GetRenderDevice(), "Media\\Bistro_Interior_cube.dds", mat, 0.04f);
        m_scenes[(int32)SceneSelectionType::LumberyardBistro]->SetSkybox(GetRenderDevice(), "Media\\Bistro_Exterior_Dark_cube.dds", mat, 0.01f);
    }

    // Deterministic SMAA temporal stress scene. This is deliberately separate
    // from the research scenes so the quality tests never modify Bistro or
    // Minecraft assets. The dark occluder moves across bright thin geometry,
    // producing controlled object-motion and disocclusion regions. The rotor
    // supplies fast diagonal subpixel edges.
    {
        shared_ptr<vaScene> scene = m_scenes[(int32)SceneSelectionType::SMAATemporalStressTest];
        scene->Clear();
        scene->Name() = "SMAA Temporal Stress Test";
        scene->SetSkybox(GetRenderDevice(), "Media\\sky_cube.dds", vaMatrix3x3::Identity, 0.015f);
        scene->Lights().push_back(std::make_shared<vaLight>(
            vaLight::MakeAmbient("TemporalTestAmbient", vaVector3(0.55f, 0.55f, 0.55f))));
        scene->Lights().push_back(std::make_shared<vaLight>(
            vaLight::MakeDirectional("TemporalTestDirectional", vaVector3(0.8f, 0.8f, 0.8f),
                vaVector3(-0.25f, 0.4f, -1.0f).Normalized())));

        auto createMaterial = [this](const vaVector4& albedo, bool doubleSided)
        {
            shared_ptr<vaRenderMaterial> material =
                GetRenderDevice().GetMaterialManager().CreateRenderMaterial(vaCore::GUIDCreate());
            material->InitializeDefaultMaterial();
            const int albedoIndex = material->FindInputByName("Albedo");
            assert(albedoIndex >= 0);
            vaRenderMaterial::MaterialInput albedoInput = material->GetInputs()[albedoIndex];
            albedoInput.Value = vaRenderMaterial::MaterialInput::ValueVar(albedo);
            material->SetInput(albedoIndex, albedoInput);
            vaRenderMaterial::MaterialSettings settings = material->GetMaterialSettings();
            settings.CastShadows = false;
            settings.ReceiveShadows = false;
            if(doubleSided)
                settings.FaceCull = vaFaceCull::None;
            material->SetMaterialSettings(settings);
            m_temporalStressMaterials.push_back(material);
            return material;
        };

        auto bindMaterial = [](const shared_ptr<vaRenderMesh>& mesh,
            const shared_ptr<vaRenderMaterial>& material)
        {
            vaRenderMesh::SubPart part = mesh->GetPart();
            part.CachedMaterialRef = material;
            part.MaterialID = material->UIDObject_GetUID();
            mesh->SetPart(part);
        };

        shared_ptr<vaRenderMaterial> brightMaterial = createMaterial(
            vaVector4(0.92f, 0.95f, 1.0f, 1.0f), false);
        shared_ptr<vaRenderMaterial> rotorMaterial = createMaterial(
            vaVector4(1.0f, 0.32f, 0.06f, 1.0f), false);
        shared_ptr<vaRenderMaterial> occluderMaterial = createMaterial(
            vaVector4(0.025f, 0.03f, 0.04f, 1.0f), false);
        shared_ptr<vaRenderMaterial> backdropMaterial = createMaterial(
            vaVector4(0.12f, 0.16f, 0.22f, 1.0f), true);

        shared_ptr<vaRenderMesh> brightCylinder = vaRenderMesh::CreateCylinder(
            GetRenderDevice(), vaMatrix4x4::Identity, 1.0f, 1.0f, 1.0f, 12, false, false);
        shared_ptr<vaRenderMesh> rotorCube = vaRenderMesh::CreateCube(
            GetRenderDevice(), vaMatrix4x4::Identity, false);
        shared_ptr<vaRenderMesh> occluderCube = vaRenderMesh::CreateCube(
            GetRenderDevice(), vaMatrix4x4::Identity, false);
        shared_ptr<vaRenderMesh> backdropPlane = vaRenderMesh::CreatePlane(
            GetRenderDevice(), vaMatrix4x4::Identity, 1.0f, 1.0f);
        bindMaterial(brightCylinder, brightMaterial);
        bindMaterial(rotorCube, rotorMaterial);
        bindMaterial(occluderCube, occluderMaterial);
        bindMaterial(backdropPlane, backdropMaterial);
        m_temporalStressMeshes = { brightCylinder, rotorCube, occluderCube, backdropPlane };

        auto createObject = [&scene](const string& name, const shared_ptr<vaRenderMesh>& mesh,
            const vaMatrix4x4& transform)
        {
            shared_ptr<vaSceneObject> object = scene->CreateObject(name, transform);
            object->AddRenderMeshRef(mesh);
            return object;
        };

        createObject("TemporalTestBackdrop", backdropPlane,
            vaMatrix4x4::Scaling(5.2f, 3.6f, 1.0f)
            * vaMatrix4x4::RotationX(0.5f * VA_PIf)
            * vaMatrix4x4::Translation(0.0f, 2.8f, 2.7f));

        // Repeated vertical and diagonal lines expose shimmer/crawling while
        // the camera translates laterally by a subpixel-sensitive distance.
        for(int lineIndex = -8; lineIndex <= 8; lineIndex++)
        {
            const float x = (float)lineIndex * 0.42f;
            createObject(vaStringTools::Format("TemporalTestVerticalLine_%02d", lineIndex + 8),
                brightCylinder,
                vaMatrix4x4::Scaling(0.024f, 0.024f, 4.6f)
                * vaMatrix4x4::Translation(x, 1.8f, 2.45f));
        }
        for(int lineIndex = -3; lineIndex <= 3; lineIndex++)
        {
            const float x = (float)lineIndex * 0.92f;
            const float angle = (lineIndex & 1)? 0.24f * VA_PIf : -0.24f * VA_PIf;
            createObject(vaStringTools::Format("TemporalTestDiagonalLine_%02d", lineIndex + 3),
                brightCylinder,
                vaMatrix4x4::Scaling(0.022f, 0.022f, 3.4f)
                * vaMatrix4x4::RotationY(angle)
                * vaMatrix4x4::Translation(x, 1.4f, 2.45f));
        }

        m_temporalStressMovingOccluder = createObject("TemporalTestMovingOccluder",
            occluderCube,
            vaMatrix4x4::Scaling(0.75f, 0.28f, 1.1f)
            * vaMatrix4x4::Translation(-2.8f, -0.2f, 1.65f));

        m_temporalStressRotorBlades.clear();
        for(int bladeIndex = 0; bladeIndex < 4; bladeIndex++)
        {
            m_temporalStressRotorBlades.push_back(createObject(
                vaStringTools::Format("TemporalTestRotorBlade_%d", bladeIndex),
                rotorCube, vaMatrix4x4::Identity));
        }
    }

    // The UNC Power Plant source is a non-commercial external research asset
    // and therefore never enters this repository.  When an explicit cache
    // path is supplied, load the selected real-geometry section into a
    // separate preview scene.  The offline converter validates the original
    // OBJ hash and writes the compact cache to the external research drive.
    m_scenes[(int32)SceneSelectionType::PowerPlantThinGeometry]->Clear();
    m_scenes[(int32)SceneSelectionType::PowerPlantThinGeometry]->Name() =
        "Power Plant Thin Geometry (external cache not loaded)";
    for(const auto& parameter : m_application.GetCommandLineParameters())
    {
        if(_wcsicmp(parameter.first.c_str(), L"smaaPowerPlantPreviewCache") != 0)
            continue;
        if(parameter.second.empty())
        {
            VA_LOG_ERROR("-smaaPowerPlantPreviewCache requires an absolute .smaapp cache path");
            break;
        }
        if(LoadPowerPlantPreviewCache(parameter.second))
        {
            m_settings.SceneChoice = SceneSelectionType::PowerPlantThinGeometry;
            m_flythroughPlay = false;
            m_camera->SetPosition(vaVector3(0.0f, -28.0f, 3.0f));
            m_camera->SetOrientationLookAt(vaVector3(0.0f, 0.0f, 0.0f));
            m_SMAA->ResetTemporalHistory();
        }
        break;
    }

    // San Miguel 2.1 is kept on the external research drive under its source
    // license. The repository's Assimp integration is disabled and its source
    // is not shipped, so load a validated external cache with texture paths.
    m_scenes[(int32)SceneSelectionType::SanMiguelTextured]->Clear();
    m_scenes[(int32)SceneSelectionType::SanMiguelTextured]->Name() =
        "San Miguel 2.1 (external OBJ not loaded)";
    for(const auto& parameter : m_application.GetCommandLineParameters())
    {
        if(_wcsicmp(parameter.first.c_str(), L"smaaSanMiguelCache") != 0)
            continue;
        if(parameter.second.empty())
        {
            VA_LOG_ERROR("-smaaSanMiguelCache requires an absolute .smaasm cache path");
            break;
        }
        if(LoadSanMiguelTexturedScene(parameter.second))
        {
            m_settings.SceneChoice = SceneSelectionType::SanMiguelTextured;
            m_flythroughPlay = false;
            // Courtyard research viewpoint.  The former exterior position at
            // y=-24 looked directly into the south wall and produced a valid
            // but useless full-frame wall-texture capture.
            m_camera->SetPosition(vaVector3(-5.0f, -10.5f, 2.3f));
            m_camera->SetOrientationLookAt(vaVector3(3.0f, -2.3f, 2.0f));
            m_SMAA->ResetTemporalHistory();
        }
        break;
    }

#ifdef ENABLE_TEXTURE_REDUCTION_TOOL
    vaTextureReductionTestTool::SetSupportedByApp();
#endif
}

const char* CMAA2Sample::GetSMAATemporalStressScenarioName(SMAATemporalStressScenario scenario)
{
    switch(scenario)
    {
    case SMAATemporalStressScenario::ThinLinesCameraPan:             return "thin-lines";
    case SMAATemporalStressScenario::ObjectMotionDisocclusion:       return "object-motion";
    case SMAATemporalStressScenario::CombinedCameraAndObjectMotion:  return "combined";
    default:                                                         return "invalid";
    }
}

void CMAA2Sample::SetSMAATemporalStressTestState(
    SMAATemporalStressScenario scenario, float timeSeconds)
{
    assert(scenario >= SMAATemporalStressScenario::ThinLinesCameraPan
        && scenario < SMAATemporalStressScenario::MaxValue);
    m_temporalStressScenario = scenario;
    m_temporalStressTimeSeconds = timeSeconds;
    m_temporalStressStateConfigured = true;
    const bool cameraMoves = scenario == SMAATemporalStressScenario::ThinLinesCameraPan
        || scenario == SMAATemporalStressScenario::CombinedCameraAndObjectMotion;
    const bool objectsMove = scenario == SMAATemporalStressScenario::ObjectMotionDisocclusion
        || scenario == SMAATemporalStressScenario::CombinedCameraAndObjectMotion;

    const float cameraPhase = timeSeconds * (2.0f * VA_PIf / 4.0f);
    const float objectPhase = timeSeconds * (2.0f * VA_PIf / 3.0f);
    const float cameraX = cameraMoves? 0.42f * vaMath::Sin(cameraPhase) : 0.0f;
    const vaVector3 cameraPosition(cameraX, -10.0f, 2.65f);
    m_camera->SetPosition(cameraPosition);
    m_camera->SetOrientationLookAt(vaVector3(cameraX, 1.3f, 2.45f));

    if(m_temporalStressMovingOccluder != nullptr)
    {
        const float occluderX = objectsMove? 2.75f * vaMath::Sin(objectPhase) : -2.8f;
        m_temporalStressMovingOccluder->SetLocalTransform(
            vaMatrix4x4::Scaling(0.75f, 0.28f, 1.1f)
            * vaMatrix4x4::Translation(occluderX, -0.2f, 1.65f));
    }

    const float rotorAngle = objectsMove? timeSeconds * 2.4f * VA_PIf : 0.17f * VA_PIf;
    for(int bladeIndex = 0; bladeIndex < (int)m_temporalStressRotorBlades.size(); bladeIndex++)
    {
        const float angle = rotorAngle + (float)bladeIndex * 0.5f * VA_PIf;
        m_temporalStressRotorBlades[bladeIndex]->SetLocalTransform(
            vaMatrix4x4::Scaling(1.25f, 0.10f, 0.075f)
            * vaMatrix4x4::RotationY(angle)
            * vaMatrix4x4::Translation(2.45f, 0.15f, 3.95f));
    }
}

const char * CMAA2Sample::GetSMAACameraMotionSceneName( SceneSelectionType scene )
{
    switch( scene )
    {
    case SceneSelectionType::LumberyardBistro:      return "bistro";
    case SceneSelectionType::MinecraftLostEmpire:   return "minecraft";
    case SceneSelectionType::PowerPlantThinGeometry:return "powerplant";
    case SceneSelectionType::SanMiguelTextured:     return "sanmiguel";
    default:                                        return "invalid";
    }
}

const char * CMAA2Sample::GetSMAACameraMotionProfileName( SMAACameraMotionProfile profile )
{
    switch( profile )
    {
    case SMAACameraMotionProfile::YawSlow360:       return "yaw-slow-360";
    case SMAACameraMotionProfile::YawFast360:       return "yaw-fast-360";
    case SMAACameraMotionProfile::YawExtreme360:    return "yaw-extreme-360";
    case SMAACameraMotionProfile::StrafeFast:       return "strafe-fast";
    case SMAACameraMotionProfile::YawStrafeFast:    return "yaw-strafe-fast";
    default:                                        return "invalid";
    }
}

int CMAA2Sample::GetSMAACameraMotionProfileFrameCount( SMAACameraMotionProfile profile )
{
    const int preMotionStillFrames = 60;
    const int postMotionStillFrames = 60;
    switch( profile )
    {
    case SMAACameraMotionProfile::YawSlow360:       return preMotionStillFrames + 240 + postMotionStillFrames;
    case SMAACameraMotionProfile::YawFast360:       return preMotionStillFrames + 60 + postMotionStillFrames;
    case SMAACameraMotionProfile::YawExtreme360:    return preMotionStillFrames + 30 + postMotionStillFrames;
    case SMAACameraMotionProfile::StrafeFast:       return preMotionStillFrames + 120 + postMotionStillFrames;
    case SMAACameraMotionProfile::YawStrafeFast:    return preMotionStillFrames + 120 + postMotionStillFrames;
    default:                                        return 0;
    }
}

void CMAA2Sample::SetSMAACameraMotionTestState(
    SceneSelectionType scene, SMAACameraMotionProfile profile, int frameIndex )
{
    assert( scene == SceneSelectionType::LumberyardBistro
        || scene == SceneSelectionType::MinecraftLostEmpire
        || scene == SceneSelectionType::PowerPlantThinGeometry
        || scene == SceneSelectionType::SanMiguelTextured );
    assert( profile >= SMAACameraMotionProfile::YawSlow360
        && profile < SMAACameraMotionProfile::MaxValue );

    const int profileFrameCount = GetSMAACameraMotionProfileFrameCount( profile );
    frameIndex = vaMath::Clamp( frameIndex, 0, vaMath::Max( 0, profileFrameCount - 1 ) );
    m_cameraMotionScene = scene;
    m_cameraMotionProfile = profile;
    m_cameraMotionFrame = frameIndex;
    m_cameraMotionStateConfigured = true;

    // These are fixed research viewpoints, not the user's persisted camera.
    // Bistro is placed inside the low-contrast interior; Minecraft reuses the
    // original overview pose that frames the translated Lost Empire asset;
    // Power Plant frames the selected normalized real-geometry section.
    vaVector3 basePosition;
    vaVector3 baseForward;
    float strafeDistance;
    if( scene == SceneSelectionType::LumberyardBistro )
    {
        basePosition = vaVector3( 4.30f, -3.20f, 1.75f );
        baseForward = vaVector3( 1.0f, 0.0f, 0.0f );
        strafeDistance = 1.50f;
    }
    else if( scene == SceneSelectionType::MinecraftLostEmpire )
    {
        basePosition = vaVector3( 4.30f, 29.20f, 14.20f );
        baseForward = (vaVector3( 6.50f, 0.0f, 8.70f ) - basePosition).Normalized( );
        strafeDistance = 10.0f;
    }
    else if( scene == SceneSelectionType::SanMiguelTextured )
    {
        basePosition = vaVector3( -5.0f, -10.5f, 2.3f );
        baseForward = (vaVector3( 3.0f, -2.3f, 2.0f ) - basePosition).Normalized( );
        strafeDistance = 8.0f;
    }
    else
    {
        basePosition = vaVector3( 0.0f, -25.0f, 2.0f );
        baseForward = (vaVector3( 1.8f, 0.0f, 0.0f ) - basePosition).Normalized( );
        strafeDistance = 6.0f;
    }

    const int preMotionStillFrames = 60;
    int motionFrameCount = 120;
    switch( profile )
    {
    case SMAACameraMotionProfile::YawSlow360:       motionFrameCount = 240; break;
    case SMAACameraMotionProfile::YawFast360:       motionFrameCount = 60;  break;
    case SMAACameraMotionProfile::YawExtreme360:    motionFrameCount = 30;  break;
    case SMAACameraMotionProfile::StrafeFast:
    case SMAACameraMotionProfile::YawStrafeFast:    motionFrameCount = 120; break;
    default:                                        assert( false );         break;
    }

    float motionT = 0.0f;
    if( frameIndex >= preMotionStillFrames )
    {
        const int motionFrame = frameIndex - preMotionStillFrames;
        motionT = motionFrame >= motionFrameCount?
            1.0f : (float)(motionFrame + 1) / (float)motionFrameCount;
    }

    const bool yawMotion = profile == SMAACameraMotionProfile::YawSlow360
        || profile == SMAACameraMotionProfile::YawFast360
        || profile == SMAACameraMotionProfile::YawExtreme360
        || profile == SMAACameraMotionProfile::YawStrafeFast;
    const bool strafeMotion = profile == SMAACameraMotionProfile::StrafeFast
        || profile == SMAACameraMotionProfile::YawStrafeFast;

    float yawAngle = yawMotion? motionT * 2.0f * VA_PIf : 0.0f;
    // Make the post-motion pose bit-identical to the pre-motion pose after a
    // complete 360-degree turn; this is required for recovery-frame metrics.
    if( motionT >= 1.0f )
        yawAngle = 0.0f;

    const float cosine = vaMath::Cos( yawAngle );
    const float sine = vaMath::Sin( yawAngle );
    const vaVector3 forward(
        baseForward.x * cosine - baseForward.y * sine,
        baseForward.x * sine + baseForward.y * cosine,
        baseForward.z );

    vaVector3 position = basePosition;
    if( strafeMotion )
    {
        const vaVector3 horizontalForward( baseForward.x, baseForward.y, 0.0f );
        const vaVector3 right = vaVector3::Cross(
            vaVector3( 0.0f, 0.0f, 1.0f ), horizontalForward ).Normalized( );
        position += right * ((motionT - 0.5f) * strafeDistance);
    }

    m_camera->SetPosition( position );
    m_camera->SetOrientationLookAt( position + forward );
}

void CMAA2Sample::OnBeforeStopped()
{
#ifdef ENABLE_TEXTURE_REDUCTION_TOOL
    if (vaTextureReductionTestTool::GetInstancePtr() != nullptr)
    {
        vaTextureReductionTestTool::GetInstance().ResetCamera(m_camera);
        delete vaTextureReductionTestTool::GetInstancePtr();
    }
#endif
    m_postProcessTonemap = nullptr;
    m_CMAA2 = nullptr;
    m_SMAA = nullptr;
    m_FXAA = nullptr;
    m_SSAccumulationColor = nullptr;
}

void CMAA2Sample::OnTick(float deltaTime)
{
    vaDrawResultFlags prevDrawResultFlags = m_currentDrawResults;
    m_currentDrawResults = vaDrawResultFlags::None;

    // if we're stuck on loading / compiling, slow down the 
    if (prevDrawResultFlags != vaDrawResultFlags::None)
        vaThreading::Sleep(30);

    ProcessCommandLineCaptureRequest();

    // External research scenes can require substantial first-use shader and
    // GPU resource preparation. AutoBench intentionally does not advance
    // while the previous render reports pending work, so enforce a wall-clock
    // deadline outside that gate to prevent an endless high-GPU-load process.
    if(m_externalScenePreviewDeadline > 0.0
        && m_application.GetTimeFromStart() >= m_externalScenePreviewNextStatusLog)
    {
        VA_LOG("External scene preview waiting: drawFlags=0x%08X, compilingShaders=%d, pendingShadowmaps=%s, remaining=%.1f s",
            (uint32)prevDrawResultFlags, vaShader::GetNumberOfCompilingShaders(),
            HasPendingShadowmapUpdates()? "yes" : "no",
            m_externalScenePreviewDeadline - m_application.GetTimeFromStart());
        m_externalScenePreviewNextStatusLog = m_application.GetTimeFromStart() + 5.0;
    }
    if(m_externalScenePreviewDeadline > 0.0
        && m_application.GetTimeFromStart() >= m_externalScenePreviewDeadline)
    {
        VA_LOG_ERROR("External scene preview exceeded the 180-second render-readiness deadline; terminating the clean test process");
        m_externalScenePreviewDeadline = -1.0;
        m_application.Quit();
        return;
    }

    // if everything was OK with the last tick we can continue with the autobench, otherwise skip the frame until everything is loaded / compiled
    if (prevDrawResultFlags == vaDrawResultFlags::None)
    {
        m_autoBench->Tick(deltaTime);
        if (m_quitAfterCommandLineCapture && !m_autoBench->IsActive())
        {
            m_quitAfterCommandLineCapture = false;
            m_application.Quit();
            return;
        }
    }

    if (m_fixedDeltaTime > 0.0f)
        deltaTime = m_fixedDeltaTime;

    m_camera->SetYFOV(m_settings.CameraYFov);

    if (m_settings.SceneChoice == CMAA2Sample::SceneSelectionType::StaticImage)
    {
        if ((m_settings.CurrentStaticImageChoice >= 0) && (m_settings.CurrentStaticImageChoice < m_staticImageList.size()) && m_staticImageFullPaths[m_settings.CurrentStaticImageChoice] != m_loadedScreenshotFullPath)
        {
            m_loadedScreenshotFullPath = m_staticImageFullPaths[m_settings.CurrentStaticImageChoice];
            m_loadedStaticImage = vaTexture::CreateFromImageFile(GetRenderDevice(), m_loadedScreenshotFullPath, vaTextureLoadFlags::PresumeDataIsSRGB);
            m_SMAA->ResetTemporalHistory();
        }
        if (m_loadedStaticImage != nullptr)
        {
            vaVector2i clientSize = m_application.GetWindowClientAreaSize();
            if ((clientSize.x != m_loadedStaticImage->GetSizeX()) || (clientSize.y != m_loadedStaticImage->GetSizeY()))
                m_application.SetWindowClientAreaSize(vaVector2i(m_loadedStaticImage->GetSizeX(), m_loadedStaticImage->GetSizeY()));
        }
    }

    bool freezeMotionAndInput = false;

#ifdef ENABLE_TEXTURE_REDUCTION_TOOL
    if (vaTextureReductionTestTool::GetInstancePtr() != nullptr && vaTextureReductionTestTool::GetInstance().IsRunningTests())
        freezeMotionAndInput = true;
#endif

    {
        std::shared_ptr<vaCameraControllerBase> wantedCameraController = (freezeMotionAndInput) ? (nullptr) : (m_cameraFreeFlightController);

        if (m_flythroughPlay)
            wantedCameraController = m_flythroughCameraController;

        if (m_camera->GetAttachedController() != wantedCameraController)
            m_camera->AttachController(wantedCameraController);
    }

#ifdef ENABLE_TEXTURE_REDUCTION_TOOL
    {
        if (vaTextureReductionTestTool::GetInstancePtr() != nullptr)
        {
            auto controller = m_camera->GetAttachedController();
            m_camera->AttachController(nullptr);
            vaTextureReductionTestTool::GetInstance().TickCPU(m_camera, m_postProcessTonemap);
            m_camera->AttachController(controller);

            if (!vaTextureReductionTestTool::GetInstance().IsEnabled())
                delete vaTextureReductionTestTool::GetInstancePtr();
        }
    }
#endif

    {
        const float minValidDelta = 0.0005f;
        if (deltaTime < minValidDelta)
        {
            // things just not correct when the framerate is so high
            VA_LOG_WARNING("frame delta time too small, clamping");
            deltaTime = minValidDelta;
        }

        const float maxValidDelta = 0.3f;
        if (deltaTime > maxValidDelta)
        {
            // things just not correct when the framerate is so low
            // VA_LOG_WARNING( "frame delta time too large, clamping" );
            deltaTime = maxValidDelta;
        }

        if (freezeMotionAndInput)
            deltaTime = 0.0f;

        m_lastDeltaTime = deltaTime;
    }

    m_camera->Tick(deltaTime, m_application.HasFocus() && !freezeMotionAndInput);

    // The free-flight controller owns the camera during the regular tick. The
    // stress capture needs an identical analytical camera pose for every mode,
    // so apply it after controller input and rebuild the camera matrices with
    // the controller temporarily detached.
    if(m_settings.SceneChoice == CMAA2Sample::SceneSelectionType::SMAATemporalStressTest
        && m_temporalStressStateConfigured)
    {
        shared_ptr<vaCameraControllerBase> previousController =
            m_camera->GetAttachedController();
        m_camera->AttachController(nullptr);
        SetSMAATemporalStressTestState(
            m_temporalStressScenario, m_temporalStressTimeSeconds);
        m_camera->Tick(0.0f, false);
        m_camera->AttachController(previousController);
    }

    if( m_cameraMotionStateConfigured && m_settings.SceneChoice == m_cameraMotionScene )
    {
        shared_ptr<vaCameraControllerBase> previousController =
            m_camera->GetAttachedController( );
        m_camera->AttachController( nullptr );
        SetSMAACameraMotionTestState(
            m_cameraMotionScene, m_cameraMotionProfile, m_cameraMotionFrame );
        m_camera->Tick( 0.0f, false );
        m_camera->AttachController( previousController );
    }

    // Scene stuff
    {
        m_settings.SceneChoice = (SceneSelectionType)vaMath::Clamp((int32)m_settings.SceneChoice, 0, (int32)_countof(m_scenes) - 1);
        shared_ptr<vaScene> newScene = m_scenes[(int32)m_settings.SceneChoice];
        if( m_currentScene != newScene )
            m_SMAA->ResetTemporalHistory();
        m_currentScene = newScene;
        assert(m_currentScene != nullptr);
        m_currentScene->Tick(deltaTime);

        // we intend to select meshes, so make sure the list for storage is created
        if (m_currentSceneMainRenderSelection.MeshList == nullptr)
            m_currentSceneMainRenderSelection.MeshList = std::make_shared<vaRenderMeshDrawList>();

        assert(m_currentSceneMainRenderSelection.MeshList->Count() == 0); // leftovers from before? shouldn't happen!

        m_currentSceneMainRenderSelection.Filter = vaRenderSelectionFilter(*m_camera);
        m_currentDrawResults |= m_currentScene->SelectForRendering(m_currentSceneMainRenderSelection);

        //////////////////////////////////////////////////////////////////////////
        // Update relevant systems from the current scene
        // Sky
        shared_ptr<vaTexture> skyboxTexture; vaMatrix3x3 skyboxRotation; float skyboxColorMultiplier;
        m_currentScene->GetSkybox(skyboxTexture, skyboxRotation, skyboxColorMultiplier);
        m_skybox->SetCubemap(skyboxTexture);
        m_skybox->Settings().Rotation = skyboxRotation;
        m_skybox->Settings().ColorMultiplier = skyboxColorMultiplier;
        // Lights
        m_currentScene->ApplyLighting(*m_lighting);
        //////////////////////////////////////////////////////////////////////////

        // just the debug 3D UI stuff (if enabled)
        m_currentScene->DrawUI(*m_camera, GetRenderDevice().GetCanvas2D(), GetRenderDevice().GetCanvas3D());
    }

    // tick lighting
    m_lighting->Tick(deltaTime);


    // do we need to redraw a shadow map?
    {
        assert(m_queuedShadowmap == nullptr); // we should have reseted it already
        m_queuedShadowmap = m_lighting->GetNextHighestPriorityShadowmapForRendering();

        // don't record shadows if assets are still loading - they will be broken
        if (m_currentDrawResults != vaDrawResultFlags::None)
            m_queuedShadowmap = nullptr;

        if (m_queuedShadowmap != nullptr)
        {
            // we intend to select meshes, so make sure the list for storage is created
            if (m_queuedShadowmapRenderSelection.MeshList == nullptr)
                m_queuedShadowmapRenderSelection.MeshList = std::make_shared<vaRenderMeshDrawList>();
            assert(m_queuedShadowmapRenderSelection.MeshList->Count() == 0); // leftovers from before? shouldn't happen!

            m_queuedShadowmapRenderSelection.Filter = vaRenderSelectionFilter(*m_queuedShadowmap);
            m_currentDrawResults |= m_currentScene->SelectForRendering(m_queuedShadowmapRenderSelection);
        }
        if (m_currentDrawResults != vaDrawResultFlags::None)
            m_queuedShadowmap = nullptr;
    }

    if (!freezeMotionAndInput && m_application.HasFocus() && !vaInputMouseBase::GetCurrent()->IsCaptured()
#ifdef VA_IMGUI_INTEGRATION_ENABLED
        && !ImGui::GetIO().WantTextInput
#endif
        )
    {
        static float notificationStopTimeout = 0.0f;
        notificationStopTimeout += deltaTime;

        vaInputKeyboardBase& keyboard = *vaInputKeyboardBase::GetCurrent();
        if (keyboard.IsKeyDown(vaKeyboardKeys::KK_LEFT) || keyboard.IsKeyDown(vaKeyboardKeys::KK_RIGHT) || keyboard.IsKeyDown(vaKeyboardKeys::KK_UP) || keyboard.IsKeyDown(vaKeyboardKeys::KK_DOWN) ||
            keyboard.IsKeyDown((vaKeyboardKeys)'W') || keyboard.IsKeyDown((vaKeyboardKeys)'S') || keyboard.IsKeyDown((vaKeyboardKeys)'A') ||
            keyboard.IsKeyDown((vaKeyboardKeys)'D') || keyboard.IsKeyDown((vaKeyboardKeys)'Q') || keyboard.IsKeyDown((vaKeyboardKeys)'E'))
        {
            if (notificationStopTimeout > 3.0f)
            {
                notificationStopTimeout = 0.0f;
                vaLog::GetInstance().Add(vaVector4(1.0f, 0.0f, 0.0f, 1.0f), L"To switch into free flight (move&rotate) mode, use mouse right click.");
            }
        }

#ifdef VA_IMGUI_INTEGRATION_ENABLED
        if (!ImGui::GetIO().WantCaptureMouse)
#endif
            m_zoomTool->HandleMouseInputs(*vaInputMouseBase::GetCurrent());
    }

#if 0 // save/load camera locations
    // let the ImgUI controls have input priority
    if (!freezeMotionAndInput && !ImGui::GetIO().WantCaptureKeyboard && (vaInputKeyboard::GetCurrent() != nullptr))
    {
        int numkeyPressed = -1;
        for (int i = 0; i <= 9; i++)
            numkeyPressed = (vaInputKeyboard::GetCurrent()->IsKeyClicked((vaKeyboardKeys)('0' + i))) ? (i) : (numkeyPressed);

        if (vaInputKeyboard::GetCurrent()->IsKeyDownOrClicked(KK_LCONTROL) && (numkeyPressed != -1))
            SaveCamera(numkeyPressed);

        if (vaInputKeyboard::GetCurrent()->IsKeyDownOrClicked(KK_LSHIFT) && (numkeyPressed != -1))
            LoadCamera(numkeyPressed);
    }
#endif

    // Do the rendering tick and present 
    {
        GetRenderDevice().BeginFrame(deltaTime);

        m_currentDrawResults |= RenderTick();

        // 스크린샷 기능 추가
        if (m_application.HasFocus() && !ImGui::GetIO().WantCaptureKeyboard)
        {
            auto keyboard = vaInputKeyboardBase::GetCurrent();

            if (keyboard->IsKeyClicked((vaKeyboardKeys)'P')) // 'P' 키 입력 시
            {
                wstring folderPath = vaCore::GetExecutableDirectory() + L"Captures\\";
                vaFileTools::EnsureDirectoryExists(folderPath);

                wstring fileName = folderPath + vaStringTools::Format(L"%s_%dx%d.png",
                    vaStringTools::SimpleWiden(GetAAName(m_settings.CurrentAAOption)).c_str(),
                    m_application.GetWindowClientAreaSize().x,
                    m_application.GetWindowClientAreaSize().y);

                auto mainContext = GetRenderDevice().GetMainContext();
                shared_ptr<vaTexture> finalTexture = m_GBuffer->GetOutputColor();

                if (finalTexture != nullptr)
                {
                    finalTexture->SaveToPNGFile(*mainContext, fileName);
                    VA_LOG_SUCCESS(L"Screenshot saved: %s", fileName.c_str());
                }
            }
        }
        // draw imgui 
        if (vaUIManager::GetInstance().IsVisible())
        {
            // Actual ImGui draw!
            GetRenderDevice().ImGuiRender(*GetRenderDevice().GetMainContext());
        }

        GetRenderDevice().EndAndPresentFrame((m_application.GetVsync()) ? (1) : (0));
    }
}

vaDrawResultFlags CMAA2Sample::DrawScene(vaCameraBase& camera, vaGBuffer& gbufferOutput, const shared_ptr<vaTexture>& gbufferColorScratch, bool& colorScratchContainsFinal, const vaViewport& mainViewport, float globalMIPOffset, const vaVector2& globalPixelScale, bool skipTonemapTick)
{
    vaDrawResultFlags drawResults = vaDrawResultFlags::None;
    vaRenderDeviceContext& mainContext = *GetRenderDevice().GetMainContext();

    mainViewport;

    // m_renderDevice.GetMaterialManager().SetTexturingDisabled( m_debugTexturingDisabled ); 

    // decide on the main render target / depth
    shared_ptr<vaTexture> mainColorRT = gbufferOutput.GetOutputColor();  // m_renderDevice->GetCurrentBackbuffer();
    shared_ptr<vaTexture> mainColorRTIgnoreSRGBConvView = gbufferOutput.GetOutputColorIgnoreSRGBConvView();  // m_renderDevice->GetCurrentBackbuffer();
    shared_ptr<vaTexture> mainDepthRT = gbufferOutput.GetDepthBuffer();

    // clear the main render target / depth
    mainColorRT->ClearRTV(mainContext, vaVector4(0.0f, 0.0f, 0.0f, 0.0f));
    mainDepthRT->ClearDSV(mainContext, true, camera.GetUseReversedZ() ? (0.0f) : (1.0f), false, 0);

    // If we're drawing the screenshot (disabled when VR enabled)
    if (m_settings.SceneChoice == CMAA2Sample::SceneSelectionType::StaticImage)
    {
        // restore main render target / depth
        mainContext.SetRenderTarget(mainColorRT, nullptr, true);

        if (m_loadedStaticImage != nullptr)
        {
            VA_SCOPE_CPUGPU_TIMER(CopyStaticImage, mainContext);
            vaSceneDrawContext drawContext(mainContext, camera, vaDrawContextOutputType::DepthOnly, vaDrawContextFlags::None, m_lighting.get());
            drawContext.GlobalMIPOffset = globalMIPOffset;
            drawContext.GlobalPixelScale = globalPixelScale;

            //mainColorRT->CopyFrom( mainContext, *m_loadedStaticImage );
            drawResults |= m_postProcess->StretchRect(mainContext, m_loadedStaticImage, vaVector4(0, 0, (float)m_loadedStaticImage->GetSizeX(), (float)m_loadedStaticImage->GetSizeY()), vaVector4(0, 0, (float)m_loadedStaticImage->GetSizeX(), (float)m_loadedStaticImage->GetSizeY()), false);

            // compute luma in the screenshot case in a separate pass, saves on complexity
            // // (not needed for SMAA only at the moment since it's using full color) 
            // if( m_settings.CurrentAAOption != CMAA2Sample::AAType::SMAA ) <- SMAA is using luma too now so that perf testing is apples to apples since qual diff is not too high
            {
                vaRenderDeviceContext::RenderOutputsState backupOutputs = mainContext.GetOutputs();
                mainContext.SetRenderTarget(m_exportedLuma, nullptr, false);
                drawResults |= m_postProcess->ComputeLumaForEdges(mainContext, backupOutputs.RenderTargets[0]);
                mainContext.SetOutputs(backupOutputs);
            }

            if (m_settings.CurrentAAOption == CMAA2Sample::AAType::CMAA2)
            {
                {
                    VA_SCOPE_CPUGPU_TIMER(CMAA2, mainContext);
                    drawResults |= m_CMAA2->Draw(mainContext, mainColorRT, m_exportedLuma);
                }
                VA_SCOPE_MAKE_LAST_SELECTED();
            }
            else if (IsSMAASingleSample(m_settings.CurrentAAOption))
            {
                {
                    VA_SCOPE_CPUGPU_TIMER(SMAA, mainContext);
                    assert(!colorScratchContainsFinal);
                    mainContext.SetRenderTarget(gbufferColorScratch, nullptr, true);
                    colorScratchContainsFinal = true;
                    //m_SMAA->Draw( mainContext, mainColorRT ); //, m_exportedLuma );
                    drawResults |= m_SMAA->Draw(mainContext, mainColorRT, m_exportedLuma, mainDepthRT, &camera);
                }
                VA_SCOPE_MAKE_LAST_SELECTED();
            }
            else if (m_settings.CurrentAAOption == CMAA2Sample::AAType::FXAA)
            {
                {
                    VA_SCOPE_CPUGPU_TIMER(FXAA, mainContext);
                    assert(!colorScratchContainsFinal);
                    mainContext.SetRenderTarget(gbufferColorScratch, nullptr, true);
                    colorScratchContainsFinal = true;
                    drawResults |= m_FXAA->Draw(mainContext, mainColorRT, m_exportedLuma);
                }
                VA_SCOPE_MAKE_LAST_SELECTED();
            }
            // 스크린샷 처리 추가 코드
            if (colorScratchContainsFinal)
            {
                // 임시 버퍼에 저장된 SMAA/FXAA 결과를 다시 화면용 버퍼(mainColorRT)로 복사
                mainContext.SetRenderTarget(mainColorRT, nullptr, true);
                drawResults |= m_postProcess->StretchRect(mainContext, gbufferColorScratch,
                    vaVector4(0, 0, (float)mainColorRT->GetSizeX(), (float)mainColorRT->GetSizeY()),
                    vaVector4(0, 0, (float)mainColorRT->GetSizeX(), (float)mainColorRT->GetSizeY()), false);
            }

        }
    }
    else
    {
        // normal scene rendering path

        // Depth pre-pass
        if (m_settings.ZPrePass)
        {
            VA_SCOPE_CPUGPU_TIMER(ZPrePass, mainContext);
            vaSceneDrawContext drawContext(mainContext, camera, vaDrawContextOutputType::DepthOnly, vaDrawContextFlags::None);
            drawContext.GlobalMIPOffset = globalMIPOffset;
            drawContext.GlobalPixelScale = globalPixelScale;

            // set main depth only
            mainContext.SetRenderTarget(nullptr, mainDepthRT, true);

            drawResults |= GetRenderDevice().GetMeshManager().Draw(drawContext, *m_currentSceneMainRenderSelection.MeshList, vaBlendMode::Opaque, vaRenderMeshDrawFlags::SkipTransparencies | vaRenderMeshDrawFlags::EnableDepthTest | vaRenderMeshDrawFlags::EnableDepthWrite);
        }

        // clear light accumulation (radiance) RT
        gbufferOutput.GetRadiance()->ClearRTV(mainContext, vaVector4(0.0f, 0.0f, 0.0f, 0.0f));

        // Forward opaque
        {
            VA_SCOPE_CPUGPU_TIMER(Forward, mainContext);

            vaSceneDrawContext drawContext(mainContext, camera, vaDrawContextOutputType::Forward, vaDrawContextFlags::None, m_lighting.get());
            drawContext.GlobalMIPOffset = globalMIPOffset; drawContext.GlobalPixelScale = globalPixelScale;

            mainContext.SetRenderTarget(gbufferOutput.GetRadiance(), mainDepthRT, true);

            vaRenderMeshDrawFlags drawFlags = vaRenderMeshDrawFlags::SkipTransparencies | vaRenderMeshDrawFlags::EnableDepthTest | vaRenderMeshDrawFlags::EnableDepthWrite;
            if (m_settings.ZPrePass)
                drawFlags |= vaRenderMeshDrawFlags::DepthTestIncludesEqual;
            drawResults |= GetRenderDevice().GetMeshManager().Draw(drawContext, *m_currentSceneMainRenderSelection.MeshList, vaBlendMode::Opaque, drawFlags);
        }

        // Always Forward - skybox, transparencies, debugging, etc.
        {
            mainContext.SetRenderTarget(gbufferOutput.GetRadiance(), mainDepthRT, true);

            //vaDebugCanvas3D::GetInstance().DrawBox( vaBoundingBox( vaVector3( -35.0f, -60.0f, -10.0f ), vaVector3( 80.0f, 90.0f, 10.24f ) ), 0xFF00FF00, 0x200000FF );

            {
                vaSceneDrawContext drawContext(mainContext, camera, vaDrawContextOutputType::Forward, vaDrawContextFlags::None, m_lighting.get());
                drawContext.GlobalMIPOffset = globalMIPOffset; drawContext.GlobalPixelScale = globalPixelScale;

                // needs to go in before transparencies - it's a hack anyway so let's just stick it in here, before the skybox
                if (m_SSAOLiteEffect != nullptr)
                    drawResults |= m_SSAOLiteEffect->Draw(drawContext, drawContext.Camera.GetProjMatrix(), mainDepthRT, true, nullptr);

                // opaque skybox
                drawResults |= m_skybox->Draw(drawContext);

                // transparencies
                {
                    // first draw into depth
                    //GetRenderDevice().GetMeshManager().Draw( drawContext, m_currentSceneMainRenderSelection.MeshList, vaRenderMaterialShaderType::Forward, vaBlendMode::Opaque, vaRenderMeshDrawFlags::SkipNonTransparencies | vaRenderMeshDrawFlags::EnableDepthTest | vaRenderMeshDrawFlags::EnableDepthWrite );

                    // then draw transparencies
                    drawResults |= GetRenderDevice().GetMeshManager().Draw(drawContext, *m_currentSceneMainRenderSelection.MeshList, vaBlendMode::AlphaBlend, vaRenderMeshDrawFlags::SkipNonTransparencies | vaRenderMeshDrawFlags::EnableDepthTest | vaRenderMeshDrawFlags::DepthTestIncludesEqual);
                }

                // debugging
                vaDebugCanvas3D& canvas3D = GetRenderDevice().GetCanvas3D();
                canvas3D; // unreferenced in Release

                //canvas3D->DrawBox( m_debugBoxPos, m_debugBoxSize, 0xFF000000, 0x20FF0000 );
//#ifdef _DEBUG
//                canvas3D.DrawAxis( vaVector3( 0, 0, 0 ), 100.0f, NULL, 0.3f );
//#endif
                GetRenderDevice().GetCanvas3D().Render(drawContext, drawContext.Camera.GetViewMatrix() * drawContext.Camera.GetProjMatrix());
            }


            if (m_settings.ShowWireframe)
            {
                VA_SCOPE_CPUGPU_TIMER(Wireframe, mainContext);
                vaSceneDrawContext drawContext(mainContext, camera, vaDrawContextOutputType::Forward, vaDrawContextFlags::SetZOffsettedProjMatrix | vaDrawContextFlags::DebugWireframePass, m_lighting.get());
                drawContext.GlobalMIPOffset = globalMIPOffset; drawContext.GlobalPixelScale = globalPixelScale;

                drawResults |= GetRenderDevice().GetMeshManager().Draw(drawContext, *m_currentSceneMainRenderSelection.MeshList, vaBlendMode::Opaque, vaRenderMeshDrawFlags::EnableDepthTest | vaRenderMeshDrawFlags::DepthTestIncludesEqual);
            }
        }

        // restore main render target / depth
        mainContext.SetRenderTarget(mainColorRT, nullptr, true);

        // Tonemap to final color & postprocess
        {
            VA_SCOPE_CPUGPU_TIMER(TonemapAndPostFX, mainContext);

            // stop unrendered items from messing auto exposure
            if (drawResults != vaDrawResultFlags::None)
                skipTonemapTick = true;

            vaPostProcessTonemap::AdditionalParams tonemapParams(m_requireDeterminism, skipTonemapTick);

            // export luma except in MSAA case
            if ((gbufferOutput.GetDepthBuffer()->GetSampleCount() == 1)) // && ( m_settings.CurrentAAOption != CMAA2Sample::AAType::SMAA ) ) <- SMAA is using luma too now so that perf testing is apples to apples since qual diff is not too high
                tonemapParams.OutExportLuma = m_exportedLuma;

            if (m_settings.MSAADebugSampleIndex != -1 && gbufferOutput.GetRadiance()->GetSampleCount() > 1)
            {
                VA_SCOPE_CPUGPU_TIMER(SingleMSSliceDebug, mainContext);
                // this is for debugging purposes - resolve radiance to one sample
                mainContext.SetRenderTarget(m_radianceTempTexture, nullptr, true);
                drawResults |= m_postProcess->DrawSingleSampleFromMSTexture(mainContext, gbufferOutput.GetRadiance(), m_settings.MSAADebugSampleIndex);
                mainContext.SetRenderTarget(mainColorRT, nullptr, true);
                drawResults |= m_postProcessTonemap->TickAndTonemap((m_requireDeterminism) ? (std::numeric_limits<float>::infinity()) : (m_lastDeltaTime), camera, mainContext, m_radianceTempTexture, tonemapParams);

                // debugging case - apply CMAA on one slice only
                if ((m_settings.CurrentAAOption == CMAA2Sample::AAType::CMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA2xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA4xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA8xPlusCMAA2))
                {
                    VA_SCOPE_CPUGPU_TIMER(CMAA2, mainContext);
                    drawResults |= m_CMAA2->Draw(mainContext, mainColorRT);
                    VA_SCOPE_MAKE_LAST_SELECTED();
                }
            }
            else
            {
                vaRenderDeviceContext::RenderOutputsState backupOutputs = mainContext.GetOutputs();

                bool msaaPPAAEnabled = (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA2xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA4xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA8xPlusCMAA2)
                    || (m_settings.CurrentAAOption == CMAA2Sample::AAType::SMAA_S2x);

                if (msaaPPAAEnabled)
                {
                    tonemapParams.OutMSTonemappedColor = m_MSTonemappedColor;
                    tonemapParams.OutMSTonemappedColorComplexityMask = m_MSTonemappedColorComplexityMask;

                    drawResults |= m_postProcessTonemap->TickAndTonemap((m_requireDeterminism) ? (std::numeric_limits<float>::infinity()) : (m_lastDeltaTime), camera, mainContext, gbufferOutput.GetRadiance(), tonemapParams);
                }
                else
                {
                    drawResults |= m_postProcessTonemap->TickAndTonemap((m_requireDeterminism) ? (std::numeric_limits<float>::infinity()) : (m_lastDeltaTime), camera, mainContext, gbufferOutput.GetRadiance(), tonemapParams);
                }

                bool ppAAApplied = false;

                // Apply CMAA!
                if ((m_settings.CurrentAAOption == CMAA2Sample::AAType::CMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA2xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA4xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA8xPlusCMAA2))
                {
                    VA_SCOPE_CPUGPU_TIMER(CMAA2, mainContext);
                    if (m_settings.CurrentAAOption == CMAA2Sample::AAType::CMAA2)
                        drawResults |= m_CMAA2->Draw(mainContext, mainColorRT, m_exportedLuma);
                    else if ((m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA2xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA4xPlusCMAA2) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA8xPlusCMAA2))
                        drawResults |= m_CMAA2->DrawMS(mainContext, mainColorRT, m_MSTonemappedColor, m_MSTonemappedColorComplexityMask);
                    //                        m_CMAA2->ApplyMS( mainContext, *mainColorRT, *m_MSTonemappedColor ); test without complexity mask - should be a bit slower but identical in functionality
                    ppAAApplied = true;
                    mainContext.SetOutputs(backupOutputs);
                }
                else if (IsSMAASingleSample(m_settings.CurrentAAOption) || (m_settings.CurrentAAOption == CMAA2Sample::AAType::SMAA_S2x))
                {
                    VA_SCOPE_CPUGPU_TIMER(SMAA, mainContext);
                    assert(!colorScratchContainsFinal);
                    mainContext.SetRenderTarget(gbufferColorScratch, nullptr, true);
                    colorScratchContainsFinal = true;
                    if (IsSMAASingleSample(m_settings.CurrentAAOption))
                        //m_SMAA->Draw( mainContext, mainColorRT ); 
                        drawResults |= m_SMAA->Draw(mainContext, mainColorRT, m_exportedLuma, mainDepthRT, &camera);
                    else if (m_settings.CurrentAAOption == CMAA2Sample::AAType::SMAA_S2x)
                        drawResults |= m_SMAA->Draw(mainContext, m_MSTonemappedColor);
                    ppAAApplied = true;
                }
                else if (m_settings.CurrentAAOption == CMAA2Sample::AAType::FXAA)
                {
                    VA_SCOPE_CPUGPU_TIMER(FXAA, mainContext);
                    assert(!colorScratchContainsFinal);
                    mainContext.SetRenderTarget(gbufferColorScratch, nullptr, true);
                    colorScratchContainsFinal = true;
                    drawResults |= m_FXAA->Draw(mainContext, mainColorRT, m_exportedLuma);
                    ppAAApplied = true;
                }

                if (ppAAApplied)
                {
                    VA_SCOPE_MAKE_LAST_SELECTED();
                }
            }

        }
    }

    // debug draw for showing depth / normals / stuff like that
#if 0
    {
        VA_SCOPE_CPUGPU_TIMER(DebugDraw, mainContext);
        vaSceneDrawContext drawContext(mainContext, camera, vaDrawContextOutputType::Forward, vaDrawContextFlags::None, m_lighting.get());
        drawContext.GlobalMIPOffset = globalMIPOffset; drawContext.GlobalPixelScale = globalPixelScale;
        if (colorScratchContainsFinal)
            mainContext.SetRenderTarget(gbufferColorScratch, nullptr, true);
        else
            mainContext.SetRenderTarget(m_GBuffer->GetOutputColor(), nullptr, false);
        m_renderingGlobals->DebugDraw(drawContext);
    }
#endif
    return drawResults;
}

vaDrawResultFlags CMAA2Sample::RenderTick()
{
    vaRenderDeviceContext& mainContext = *GetRenderDevice().GetMainContext();

    // this is "comparer stuff" and the main render target stuff
    vaViewport mainViewport = mainContext.GetViewport();

    m_camera->SetViewportSize(mainViewport.Width, mainViewport.Height);

    const vaSMAAWrapper::SpatialSearch spatialSMAASearch = GetSMAASpatialSearchForAAType( m_settings.CurrentAAOption );
    m_SMAA->SetSpatialSearch( spatialSMAASearch );
    const vaSMAAWrapper::TemporalSettings temporalSMAASettings = GetSMAATemporalSettingsForAAType( m_settings.CurrentAAOption );
    m_SMAA->SetTemporalSettings( temporalSMAASettings );
    const vaVector2i temporalViewportSize( (int)mainViewport.Width, (int)mainViewport.Height );
    if( temporalSMAASettings.Coverage != vaSMAAWrapper::TemporalCoverage::Disabled )
    {
        // Resource recreation inside Draw resets the temporal frame index.
        // Detect a viewport resize before choosing this frame's projection
        // jitter so the camera and reset history start on the same T2X phase.
        if( m_lastSMAATemporalViewportSize != temporalViewportSize )
            m_SMAA->ResetTemporalHistory( );
        m_lastSMAATemporalViewportSize = temporalViewportSize;
    }
    else
        m_lastSMAATemporalViewportSize = vaVector2i( 0, 0 );
    const bool temporalSMAAJitterEnabled = m_SMAA->GetTemporalJitterEnabled( );
    const bool edgeSelectiveProfile = temporalSMAASettings.Coverage == vaSMAAWrapper::TemporalCoverage::EdgeSelective;
    const vaSMAAWrapper::HistorySampler effectiveSampler = edgeSelectiveProfile?
        m_SMAA->GetEffectiveHistorySampler( ) : temporalSMAASettings.Sampler;
    const vaSMAAWrapper::HistoryClipping effectiveClipping = edgeSelectiveProfile?
        m_SMAA->GetEffectiveHistoryClipping( ) : temporalSMAASettings.Clipping;
    if( IsSMAASingleSample( m_settings.CurrentAAOption ) && m_lastLoggedSMAAOption != m_settings.CurrentAAOption )
    {
        VA_LOG( "SMAA profile '%s': spatial=%s, coverage=%s, reprojection=%s, jitter=%s, sampler=%s%s, clipping=%s%s, nonCandidateBase=%s, candidates=%s%s, expansion=%s%s, historyWeight=%.3f, nonDominantRemoval=%.3f, edgeThreshold=%.6f",
            GetAAName( m_settings.CurrentAAOption ),
            GetSpatialSearchName( spatialSMAASearch ),
            GetTemporalCoverageName( temporalSMAASettings.Coverage ),
            GetReprojectionModeName( temporalSMAASettings.Reprojection ),
            GetJitterPolicyName( temporalSMAASettings.Jitter ),
            GetHistorySamplerName( effectiveSampler ),
            edgeSelectiveProfile && m_SMAA->GetHistorySamplerOverrideEnabled( )? " [diagnostic override]" : "",
            GetHistoryClippingName( effectiveClipping ),
            edgeSelectiveProfile && m_SMAA->GetHistoryClippingOverrideEnabled( )? " [diagnostic override]" : "",
            GetNonCandidateBaseName( temporalSMAASettings.NonCandidate ),
            GetCandidatePolicyName( m_SMAA->GetEffectiveCandidatePolicy( ) ),
            m_SMAA->GetCandidatePolicyOverrideEnabled( )? " [diagnostic override]" : "",
            GetCandidateExpansionName( m_SMAA->GetEffectiveCandidateExpansion( ) ),
            m_SMAA->GetCandidateExpansionOverrideEnabled( )? " [diagnostic override]" : "",
            temporalSMAASettings.HistoryWeight,
            temporalSMAASettings.NonDominantRemovalAmount,
            temporalSMAASettings.EdgeThreshold );
        m_lastLoggedSMAAOption = m_settings.CurrentAAOption;
    }
    else if( !IsSMAASingleSample( m_settings.CurrentAAOption ) )
    {
        m_lastLoggedSMAAOption = CMAA2Sample::AAType::MaxValue;
    }

    vaCameraBase temporalCamera = *m_camera;
    vaCameraBase * sceneCamera = m_camera.get();
    if( temporalSMAAJitterEnabled && m_settings.SceneChoice != CMAA2Sample::SceneSelectionType::StaticImage )
    {
        vaVector2 jitterOffset = m_SMAA->GetTemporalJitterOffset( );
        temporalCamera.SetSubpixelOffset( jitterOffset );
        temporalCamera.Tick( 0.0f, false );
        sceneCamera = &temporalCamera;
    }

    bool colorScratchContainsFinal = false;

    vaDrawResultFlags drawResults = vaDrawResultFlags::None;

    {
        // update GBuffer resources if needed

        int msaaSampleCount = GetMSAACountForAAType(m_settings.CurrentAAOption);

        m_settings.MSAADebugSampleIndex = vaMath::Clamp(m_settings.MSAADebugSampleIndex, -1, msaaSampleCount - 1);

        m_GBuffer->UpdateResources(mainViewport.Width, mainViewport.Height, msaaSampleCount, m_GBufferFormats);

        if (m_scratchPostProcessColor == nullptr || m_scratchPostProcessColor->GetSizeX() != m_GBuffer->GetOutputColor()->GetSizeX() || m_scratchPostProcessColor->GetSizeY() != m_GBuffer->GetOutputColor()->GetSizeY() || m_scratchPostProcessColor->GetResourceFormat() != m_GBuffer->GetOutputColor()->GetResourceFormat())
        {
            m_scratchPostProcessColor = vaTexture::Create2D(GetRenderDevice(), m_GBuffer->GetOutputColor()->GetResourceFormat(), m_GBuffer->GetOutputColor()->GetSizeX(), m_GBuffer->GetOutputColor()->GetSizeY(), 1, 1, 1, vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource | vaResourceBindSupportFlags::UnorderedAccess, vaResourceAccessFlags::Default,
                m_GBuffer->GetOutputColor()->GetSRVFormat(), m_GBuffer->GetOutputColor()->GetRTVFormat(), m_GBuffer->GetOutputColor()->GetDSVFormat(), vaResourceFormatHelpers::StripSRGB(m_GBuffer->GetOutputColor()->GetSRVFormat()));
            // m_scratchPostProcessColorIgnoreSRGBConvView = vaTexture::CreateView( *m_scratchPostProcessColor, m_scratchPostProcessColor->GetBindSupportFlags(), 
            //     vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetSRVFormat() ), vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetRTVFormat() ), vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetDSVFormat() ), vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetUAVFormat() ) );
        }

        if (m_exportedLuma == nullptr || m_exportedLuma->GetSizeX() != m_GBuffer->GetOutputColor()->GetSizeX() || m_exportedLuma->GetSizeY() != m_GBuffer->GetOutputColor()->GetSizeY())
        {
            m_exportedLuma = vaTexture::Create2D(GetRenderDevice(), vaResourceFormat::R8_UNORM, m_GBuffer->GetRadiance()->GetSizeX(), m_GBuffer->GetRadiance()->GetSizeY(), 1, 1, 1, vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::UnorderedAccess | vaResourceBindSupportFlags::ShaderResource, vaResourceAccessFlags::Default);
            //m_exportedLuma->ClearUAV( mainContext, vaVector4( 0.5f, 0.0f, 0.0f, 0.0f ) );
        }

        if (msaaSampleCount > 1)
        {
            if (m_radianceTempTexture == nullptr || m_radianceTempTexture->GetSizeX() != m_GBuffer->GetRadiance()->GetSizeX() || m_radianceTempTexture->GetSizeY() != m_GBuffer->GetRadiance()->GetSizeY() || m_radianceTempTexture->GetResourceFormat() != m_GBuffer->GetRadiance()->GetResourceFormat())
                m_radianceTempTexture = vaTexture::Create2D(GetRenderDevice(), m_GBuffer->GetRadiance()->GetResourceFormat(), m_GBuffer->GetRadiance()->GetSizeX(), m_GBuffer->GetRadiance()->GetSizeY(), 1, 1, 1, vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource, vaResourceAccessFlags::Default, m_GBuffer->GetRadiance()->GetSRVFormat(), m_GBuffer->GetRadiance()->GetRTVFormat());

            m_MSTonemappedColorLastUsed = 0;

            // since we're writing to m_MSTonemappedColor as an UAV, make sure the formats are supported; this below presumes that there is support for typed UAV store (writes) to
            // R8G8B8A8_UNORM but NO support for _SRGB (which is most common scenario as of early 2018, as far as I'm aware); other cases will be handled as they come up.
            vaResourceFormat resF, uavF, srvF;
            switch (m_GBuffer->GetOutputColor()->GetSRVFormat())
            {
            case(vaResourceFormat::R8G8B8A8_UNORM_SRGB): resF = vaResourceFormat::R8G8B8A8_TYPELESS; uavF = vaResourceFormat::R8G8B8A8_UNORM; srvF = vaResourceFormat::R8G8B8A8_UNORM_SRGB; break;
            default:
                resF = uavF = srvF = m_GBuffer->GetOutputColor()->GetSRVFormat();
            }

            if (m_MSTonemappedColor == nullptr || m_MSTonemappedColor->GetSizeX() != m_GBuffer->GetRadiance()->GetSizeX() || m_MSTonemappedColor->GetSizeY() != m_GBuffer->GetRadiance()->GetSizeY() || m_MSTonemappedColor->GetArrayCount() != m_GBuffer->GetRadiance()->GetSampleCount()
                || m_MSTonemappedColor->GetResourceFormat() != resF || m_MSTonemappedColor->GetUAVFormat() != uavF || m_MSTonemappedColor->GetSRVFormat() != srvF)
            {
                m_MSTonemappedColor = vaTexture::Create2D(GetRenderDevice(), resF, m_GBuffer->GetRadiance()->GetSizeX(), m_GBuffer->GetRadiance()->GetSizeY(), 1, m_GBuffer->GetRadiance()->GetSampleCount(), 1, vaResourceBindSupportFlags::UnorderedAccess | vaResourceBindSupportFlags::ShaderResource, vaResourceAccessFlags::Default, srvF, vaResourceFormat::Automatic, vaResourceFormat::Automatic, uavF);
                // //m_MSTonemappedColorComplexityMask = vaTexture::Create2D( vaResourceFormat::R8_UINT, (m_GBuffer->GetRadiance()->GetSizeX()+1)/2, (m_GBuffer->GetRadiance()->GetSizeY()+1)/2, 1, 1, 1, vaResourceBindSupportFlags::UnorderedAccess | vaResourceBindSupportFlags::ShaderResource );
                m_MSTonemappedColorComplexityMask = vaTexture::Create2D(GetRenderDevice(), vaResourceFormat::R8_UNORM, m_GBuffer->GetRadiance()->GetSizeX(), m_GBuffer->GetRadiance()->GetSizeY(), 1, 1, 1, vaResourceBindSupportFlags::UnorderedAccess | vaResourceBindSupportFlags::ShaderResource);
            }
        }
    }

    // draw shadowmaps if needed
    if (m_queuedShadowmap != nullptr)
    {
        drawResults |= m_queuedShadowmap->Draw(mainContext, m_queuedShadowmapRenderSelection);
        m_queuedShadowmap = nullptr;
        m_queuedShadowmapRenderSelection.Reset();
    }

    if (m_settings.CurrentAAOption == CMAA2Sample::AAType::SuperSampleReference)
    {
        m_SSBuffersLastUsed = 0;

        if (m_SSAccumulationColor == nullptr || m_SSAccumulationColor->GetSizeX() != m_GBuffer->GetResolution().x || m_SSAccumulationColor->GetSizeY() != m_GBuffer->GetResolution().y)
            m_SSAccumulationColor = vaTexture::Create2D(GetRenderDevice(), vaResourceFormat::R16G16B16A16_FLOAT, m_GBuffer->GetResolution().x, m_GBuffer->GetResolution().y, 1, 1, 1, vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource);

        m_SSAccumulationColor->ClearRTV(mainContext, vaVector4(0, 0, 0, 0));

        if (m_SSGBuffer == nullptr || m_SSGBuffer->GetResolution() != m_GBuffer->GetResolution() * m_SSResScale || m_SSGBuffer->GetSampleCount() != m_GBuffer->GetSampleCount() || m_SSGBuffer->GetFormats() != m_GBuffer->GetFormats())
        {
            m_SSGBuffer = VA_RENDERING_MODULE_CREATE_SHARED(vaGBuffer, GetRenderDevice());
            m_SSGBuffer->UpdateResources(m_GBuffer->GetResolution().x * m_SSResScale, m_GBuffer->GetResolution().y * m_SSResScale, m_GBuffer->GetSampleCount(), m_GBuffer->GetFormats(), m_GBuffer->GetDeferredEnabled());
        }
        if (m_SSScratchColor == nullptr || m_SSScratchColor->GetSizeX() != m_SSGBuffer->GetOutputColor()->GetSizeX() || m_SSScratchColor->GetSizeY() != m_SSGBuffer->GetOutputColor()->GetSizeY() || m_SSScratchColor->GetResourceFormat() != m_SSGBuffer->GetOutputColor()->GetResourceFormat())
        {
            m_SSScratchColor = vaTexture::Create2D(GetRenderDevice(), m_SSGBuffer->GetOutputColor()->GetResourceFormat(), m_SSGBuffer->GetOutputColor()->GetSizeX(), m_SSGBuffer->GetOutputColor()->GetSizeY(), 1, 1, 1, vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource | vaResourceBindSupportFlags::UnorderedAccess, vaResourceAccessFlags::Default,
                m_SSGBuffer->GetOutputColor()->GetSRVFormat(), m_SSGBuffer->GetOutputColor()->GetRTVFormat(), m_SSGBuffer->GetOutputColor()->GetDSVFormat(), vaResourceFormatHelpers::StripSRGB(m_SSGBuffer->GetOutputColor()->GetSRVFormat()));
        }

        vaVector2 globalPixelScale = vaVector2::ComponentDiv(vaVector2(m_SSGBuffer->GetResolution()), vaVector2(m_GBuffer->GetResolution()));

        // SS messes up with pixel size which messes up with specular as it is based on ddx/ddy so compensate a bit here
        globalPixelScale = vaMath::Lerp(globalPixelScale, vaVector2(1.0f, 1.0f), m_SSDDXDDYBias);

        float stepX = 1.0f / (float)m_SSGridRes;
        float stepY = 1.0f / (float)m_SSGridRes;
        float addMult = 1.0f / (m_SSGridRes * m_SSGridRes);
        for (int jx = 0; jx < m_SSGridRes; jx++)
        {
            for (int jy = 0; jy < m_SSGridRes; jy++)
            {
                vaVector2 offset((jx + 0.5f) * stepX - 0.5f, (jy + 0.5f) * stepY - 0.5f);

                // vaVector2 rotatedOffset( offsetO.x * angleC - offsetO.y * angleS, offsetO.x * angleS + offsetO.y * angleC );

                // instead of angle-based rotation, do this weird grid shift
                offset.x += offset.y * stepX;
                offset.y += offset.x * stepY;

                mainContext.SetRenderTarget(m_SSGBuffer->GetOutputColor(), nullptr, true);

                vaCameraBase jitterCamera = *m_camera;
                jitterCamera.SetViewportSize(m_SSGBuffer->GetResolution().x, m_SSGBuffer->GetResolution().y);
                jitterCamera.SetSubpixelOffset(offset);
                jitterCamera.Tick(0, false);

                bool dummy = false;
                drawResults |= DrawScene(jitterCamera, *m_SSGBuffer, nullptr, dummy, mainViewport, m_SSMIPBias, globalPixelScale, jx != 0 || jy != 0);
                assert(!dummy);

                mainContext.SetRenderTarget(m_SSAccumulationColor, nullptr, true);

                if (m_SSResScale == 4)
                {
                    // first downsample from 4x4 to 1x1
                    drawResults |= m_postProcess->Downsample4x4to1x1(mainContext, m_GBuffer->GetOutputColor(), m_SSGBuffer->GetOutputColor(), 0.0f);

                    // then accumulate
                    drawResults |= m_postProcess->StretchRect(mainContext, m_GBuffer->GetOutputColor(), vaVector4(0.0f, 0.0f, (float)m_GBuffer->GetResolution().x, (float)m_GBuffer->GetResolution().y),
                        vaVector4(0.0f, 0.0f, (float)mainViewport.Width, (float)mainViewport.Height), true, vaBlendMode::Additive, vaVector4(addMult, addMult, addMult, addMult));
                }
                else
                {
                    assert(m_SSResScale == 1 || m_SSResScale == 2);

                    // downsample and accumulate
                    drawResults |= m_postProcess->StretchRect(mainContext, m_SSGBuffer->GetOutputColor(), vaVector4(0.0f, 0.0f, (float)m_SSGBuffer->GetResolution().x, (float)m_SSGBuffer->GetResolution().y),
                        vaVector4(0.0f, 0.0f, (float)mainViewport.Width, (float)mainViewport.Height), true, vaBlendMode::Additive, vaVector4(addMult, addMult, addMult, addMult));
                }
            }
        }
        // copy from accumulation
        mainContext.SetRenderTarget(m_scratchPostProcessColor, nullptr, true);
        drawResults |= m_postProcess->StretchRect(mainContext, m_SSAccumulationColor, vaVector4(0.0f, 0.0f, (float)mainViewport.Width, (float)mainViewport.Height), vaVector4(0.0f, 0.0f, (float)mainViewport.Width, (float)mainViewport.Height), true, vaBlendMode::Opaque);

        // sharpen
        drawResults |= m_postProcess->SimpleBlurSharpen(mainContext, m_GBuffer->GetOutputColor(), m_scratchPostProcessColor, m_SSSharpen);

        // restore to old RT
        mainContext.SetRenderTarget(m_GBuffer->GetOutputColor(), nullptr, true);
    }
    else
    {
        m_SSGBuffer = nullptr;

        drawResults |= DrawScene(*sceneCamera, *m_GBuffer, m_scratchPostProcessColor, colorScratchContainsFinal, mainViewport, 0.0f);
    }

    {
        vaSceneDrawContext drawContext(mainContext, *m_camera, vaDrawContextOutputType::DepthOnly);

        // 3D cursor stuff -> maybe best to do it before transparencies
#if 1
        if (!m_autoBench->IsActive())
        {
            vaVector2i mousePos = vaInputMouse::GetInstance().GetCursorClientPosDirect();

            GetRenderDevice().GetRenderGlobals().Update3DCursor(drawContext, m_GBuffer->GetDepthBuffer(), (vaVector2)mousePos);
            vaVector4 mouseCursorWorld = GetRenderDevice().GetRenderGlobals().GetLast3DCursorInfo();
            m_mouseCursor3DWorldPosition = mouseCursorWorld.AsVec3();
            // GetRenderDevice().GetCanvas3D().DrawSphere( mouseCursorWorld.AsVec3(), 0.1f, 0xFF0000FF ); //, 0xFFFFFFFF );

            // since this is where we got the info, inform scene about any clicks here to reduce lag - not really a "rendering" type of call though
            if (m_currentScene != nullptr
#ifdef VA_IMGUI_INTEGRATION_ENABLED
                && !ImGui::GetIO().WantCaptureMouse
#endif
                && vaInputMouseBase::GetCurrent()->IsKeyClicked(MK_Left))
                m_currentScene->OnMouseClick(m_mouseCursor3DWorldPosition);
        }
#endif
    }

    // we haven't used supersampling for x frames? release the texture
    m_SSBuffersLastUsed++;
    if (m_SSBuffersLastUsed > 1)
    {
        m_SSAccumulationColor = nullptr;
        m_SSScratchColor = nullptr;
        m_SSGBuffer = nullptr;
    }

    m_MSTonemappedColorLastUsed++;
    if (m_MSTonemappedColorLastUsed > 1)
    {
        m_MSTonemappedColor = nullptr;
        m_MSTonemappedColorComplexityMask = nullptr;
    }

    // draw selection no longer needed
    m_currentSceneMainRenderSelection.Reset();


    //if( m_settings.CurrentAAOption == CMAA2Sample::AAType::ExperimentalSlot2 ) 
    //{
    //    VA_SCOPE_CPUGPU_TIMER( Experimental2, mainContext );
    //
    //    const shared_ptr<vaTexture> & src = (colorScratchContainsFinal)?(m_scratchPostProcessColor):(m_GBuffer->GetOutputColor( ));
    //    const shared_ptr<vaTexture> & dst = (colorScratchContainsFinal)?(m_GBuffer->GetOutputColor( )):(m_scratchPostProcessColor);
    //
    //    static float hue        = 0.1f;
    //    static float saturation = 0.5f;
    //    static float brightness = 0.2f;
    //    static float contrast   = -0.01f;
    //    // ImGui::InputFloat( "Hue", &hue, 0.1f );
    //    // ImGui::InputFloat( "Saturation", &saturation, 0.1f );
    //    // ImGui::InputFloat( "Brightness", &brightness, 0.1f );
    //    // ImGui::InputFloat( "Contrast", &contrast, 0.1f );
    //    // hue        = vaMath::Clamp( hue,           -1.0f, 1.0f );
    //    // saturation = vaMath::Clamp( saturation,    -1.0f, 1.0f );
    //    // brightness = vaMath::Clamp( brightness,    -1.0f, 1.0f );
    //    // contrast   = vaMath::Clamp( contrast,      -1.0f, 1.0f );
    //
    //    m_postProcess->ColorProcessHSBC( mainContext, *finalOutColor, hue, saturation, brightness, contrast );
    //    colorScratchContainsFinal = !colorScratchContainsFinal;
    //}


    shared_ptr<vaTexture> finalOutColor = m_GBuffer->GetOutputColor();
    shared_ptr<vaTexture> finalOutColorIgnoreSRGBConvView = m_GBuffer->GetOutputColorIgnoreSRGBConvView();
    if (colorScratchContainsFinal)
    {
        finalOutColor = m_scratchPostProcessColor;
        finalOutColorIgnoreSRGBConvView = m_scratchPostProcessColor; //m_scratchPostProcessColorIgnoreSRGBConvView;
    }

    // various helper tools - at one point these should go and become part of the base app but for now let's just stick them in here
    {
        if (drawResults == vaDrawResultFlags::None && m_imageCompareTool != nullptr)
        {
            if (m_autoBench->IsCapturingFrame() && m_lighting->GetNextHighestPriorityShadowmapForRendering() != nullptr)
            {
                VA_WARN("Autobench active but light shadowmaps still updating - this will cause inconsistency in the results!");
            }
            m_autoBench->OnRenderComparePoint(*m_imageCompareTool, mainContext, finalOutColor, m_postProcess);
            m_imageCompareTool->RenderTick(mainContext, finalOutColor, m_postProcess);
        }

        if (!m_autoBench->IsActive())
            m_zoomTool->Draw(mainContext, finalOutColorIgnoreSRGBConvView);

#ifdef ENABLE_TEXTURE_REDUCTION_TOOL
        // show vaTextureReductionTestTool if active
        if (vaTextureReductionTestTool::GetInstancePtr() != nullptr)
        {
            vaTextureReductionTestTool::GetInstance().TickGPU(mainContext, *m_GBuffer->GetOutputColor(), m_postProcess);
            vaTextureReductionTestTool::GetInstance().DrawUI(m_camera);
        }
#endif
    }

    // restore main display buffers
    mainContext.SetRenderTarget(GetRenderDevice().GetCurrentBackbuffer(), nullptr, true);

    // Final apply to screen (redundant copy for now, leftover from expanded screen thing)
    if (drawResults != vaDrawResultFlags::ShadersStillCompiling || !m_autoBench->IsActive()) // prevent flashing during benchmarking due to shader compilation - looks ugly
    {
        VA_SCOPE_CPUGPU_TIMER(FinalApply, mainContext);

        m_postProcess->StretchRect(mainContext, finalOutColor, vaVector4((float)0.0f, (float)0.0f, (float)mainViewport.Width, (float)mainViewport.Height), vaVector4(0.0f, 0.0f, (float)mainViewport.Width, (float)mainViewport.Height), false);
        //mainViewport = mainViewportBackup;
    }

    {
        VA_SCOPE_CPUGPU_TIMER(DebugCanvas2D, mainContext);
        GetRenderDevice().GetCanvas2D().Render(mainContext, mainViewport.Width, mainViewport.Height);
    }


    // keyboard-based selection
    {
        if (m_application.HasFocus() && !vaInputMouseBase::GetCurrent()->IsCaptured()
#ifdef VA_IMGUI_INTEGRATION_ENABLED
            && !ImGui::GetIO().WantCaptureKeyboard
#endif
            )
        {
            auto keyboard = vaInputKeyboardBase::GetCurrent();
            if (!keyboard->IsKeyDown(vaKeyboardKeys::KK_SHIFT) && !keyboard->IsKeyDown(vaKeyboardKeys::KK_CONTROL) && !keyboard->IsKeyDown(vaKeyboardKeys::KK_ALT))
            {
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'1'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::None;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'2'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::FXAA;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'3'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::CMAA2;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'4'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::SMAA;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'T'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::SMAA_O_T2X;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'R'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::SMAA_O_T2X_R;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'E'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'H'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X_R;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'5'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::MSAA2x;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'6'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::MSAA2xPlusCMAA2;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'7'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::SMAA_S2x;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'8'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::MSAA4x;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'9'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::MSAA4xPlusCMAA2;
                if (keyboard->IsKeyClicked((vaKeyboardKeys)'0'))       m_settings.CurrentAAOption = CMAA2Sample::AAType::MSAA8x;
                if (keyboard->IsKeyClicked(vaKeyboardKeys::KK_OEM_MINUS))m_settings.CurrentAAOption = CMAA2Sample::AAType::MSAA8xPlusCMAA2;
                if (keyboard->IsKeyClicked(vaKeyboardKeys::KK_OEM_PLUS)) m_settings.CurrentAAOption = CMAA2Sample::AAType::SuperSampleReference;
                if (keyboard->IsKeyClicked(vaKeyboardKeys::KK_F8) && !m_autoBench->IsActive())
                    m_queueEightCasePerformanceBenchmark = true;
            }
        }
    }

    return drawResults;
}

void CMAA2Sample::OnSerializeSettings(vaXMLSerializer& serializer)
{
    m_settings.Serialize(serializer);

    // just disable this by default always, not worth saving it, causes confusion
    if (serializer.IsReading())
        m_settings.MSAADebugSampleIndex = -1;
}

class BenchItemDelay : public AutoBenchToolWorkItem
{
    float           m_remainingTime;

public:
    BenchItemDelay(CMAA2Sample& parent, float time) : AutoBenchToolWorkItem(parent), m_remainingTime(time) {}

protected:
    virtual void    Tick(AutoBenchTool&, float deltaTime) override { m_remainingTime -= deltaTime; VA_LOG("remaining time: %.3f", m_remainingTime); }
    virtual void    OnRender(AutoBenchTool&) override {}
    virtual bool    IsDone(AutoBenchTool&) const override { return m_remainingTime <= 0; }
    virtual float   GetProgress() const override { return 0.5f; }
};

class BenchItemCaptureSMAAExternalScenePreview : public AutoBenchToolWorkItem
{
    const CMAA2Sample::SceneSelectionType m_scene;
    const int       m_warmupFrameCount;
    const wstring   m_outputFileName;
    const string    m_reportTitle;
    int             m_currentFrame = 0;
    bool            m_started = false;
    bool            m_renderReady = false;
    bool            m_isDone = false;
    bool            m_captureSucceeded = false;
    wstring         m_outputPath;

public:
    BenchItemCaptureSMAAExternalScenePreview(CMAA2Sample& parent,
        CMAA2Sample::SceneSelectionType scene, int warmupFrameCount,
        const wstring& outputFileName, const string& reportTitle)
        : AutoBenchToolWorkItem(parent),
        m_scene(scene),
        m_warmupFrameCount(vaMath::Clamp(warmupFrameCount, 0, 600)),
        m_outputFileName(outputFileName),
        m_reportTitle(reportTitle)
    {
    }

protected:
    virtual void Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;
        // Reuse the camera-motion test state so OnTick reapplies the fixed
        // analytical pose after free-flight input and rebuilds its matrices.
        // Merely setting the camera here is too early: the normal controller
        // update later in OnTick would restore the persisted user pose.
        if(m_scene == CMAA2Sample::SceneSelectionType::SanMiguelTextured)
            m_parent.SetSMAACameraMotionTestState(
                m_scene, CMAA2Sample::SMAACameraMotionProfile::YawSlow360, 0);
        if(!m_started)
        {
            m_started = true;
            m_parent.Settings().SceneChoice = m_scene;
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA;
            m_parent.SetRequireDeterminism(true);
            m_parent.SetFixedDeltaTime(1.0f / 60.0f);
            m_parent.SetSMAAPreset(vaSMAAWrapper::Preset::PRESET_ULTRA);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity();
            abTool.ReportStart();
            m_outputPath = abTool.ReportGetDir() + m_outputFileName;
            abTool.ReportAddText(m_reportTitle + "\r\n");
            abTool.ReportAddText("Classification: engineering scene-selection evidence\r\n");
            abTool.ReportAddText("SMAA preset: Ultra\r\n");
            abTool.ReportAddText(vaStringTools::Format(
                "Warm-up: %d frames\r\n", m_warmupFrameCount));
            m_currentFrame = -m_warmupFrameCount;
        }
        else
        {
            if(!m_renderReady)
            {
                if(vaShader::GetNumberOfCompilingShaders() != 0
                    || m_parent.HasPendingShadowmapUpdates())
                    return;
                m_renderReady = true;
                VA_LOG("External scene render preparation complete; starting %d warm-up frames",
                    m_warmupFrameCount);
                return;
            }
            m_currentFrame++;
            if(m_currentFrame > 0)
            {
                abTool.ReportAddText(
                    string("Capture: ") + (m_captureSucceeded? "PASS" : "FAIL") + "\r\n");
                abTool.ReportFinish();
                m_parent.SetFixedDeltaTime(0.0f);
                m_parent.SetRequireDeterminism(false);
                if(m_scene == CMAA2Sample::SceneSelectionType::SanMiguelTextured)
                    m_parent.ClearSMAACameraMotionTestState();
                m_isDone = true;
            }
        }
    }

    virtual void OnRender(AutoBenchTool&) override {}

    virtual void OnRenderComparePoint(AutoBenchTool& abTool, vaImageCompareTool&,
        vaRenderDeviceContext& renderContext, const shared_ptr<vaTexture>& colorInOut,
        shared_ptr<vaPostProcess>&) override
    {
        if(m_currentFrame == 0 && !m_captureSucceeded)
        {
            const vaVector3 cameraPosition = m_parent.Camera()->GetPosition();
            abTool.ReportAddText(vaStringTools::Format(
                "SceneChoice: %d, requested scene: %d\r\n",
                (int)m_parent.Settings().SceneChoice, (int)m_scene));
            abTool.ReportAddText(vaStringTools::Format(
                "Capture camera: %.3f, %.3f, %.3f\r\n",
                cameraPosition.x, cameraPosition.y, cameraPosition.z));
            m_captureSucceeded = colorInOut->SaveToPNGFile(renderContext, m_outputPath);
            if(!m_captureSucceeded)
                VA_LOG_ERROR(L"Failed to save external scene preview '%s'", m_outputPath.c_str());
        }
    }

    virtual bool IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual bool IsCapturingFrame() const override
        { return m_renderReady && m_currentFrame == 0; }
    virtual float GetProgress() const override
    {
        return m_started? vaMath::Clamp(
            (float)(m_currentFrame + m_warmupFrameCount + 1)
                / (float)(m_warmupFrameCount + 2), 0.0f, 1.0f) : 0.0f;
    }
};

class BenchItemPerformance : public AutoBenchToolWorkItem
{
public:
    static const int    c_framePerSecond = 30;

private:
    const int           c_warmupLoops = 2;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const int           c_totalFrameCount;
    vector<float>       m_totalTimePerAAOption;
    vaSystemTimer       m_timer;
    int                 m_currentAAOption;
    bool                m_isDone;
    int                 m_currentFrame;

    // static images에서도 밴치마크 가능하게 수정
public:
    BenchItemPerformance(CMAA2Sample& parent) : AutoBenchToolWorkItem(parent), m_currentFrame(-1), m_currentAAOption(-c_warmupLoops - 1),
        c_totalFrameCount((parent.Settings().SceneChoice == CMAA2Sample::SceneSelectionType::StaticImage) ? (16000) : (int)(parent.GetFlythroughCameraController()->GetTotalTime() / c_frameDeltaTime)),
        m_isDone(false) {
    }

protected:
    virtual void    Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;

        // 테스트하고 싶은 범위 정의 (Enum 순서 기준)
        const int startAA = (int)CMAA2Sample::AAType::None;  // 시작 (0)
        const int endAA = (int)CMAA2Sample::AAType::SMAA;  // 끝 (3)

        // Init on start
        // 초기화 부분 (Tick 함수 내)
        if (m_currentAAOption == (-c_warmupLoops - 1))
        {
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::None;
            vector<string> columns;
            columns.push_back(vaStringTools::Format("(total frames %d)", c_totalFrameCount));
            for (int i = 0; i < c_warmupLoops; i++)
                columns.push_back(vaStringTools::Format("Warmup loop %d", i));

            // 인덱스 범위를 루프로 돌며 컬럼 헤더 생성
            for (int i = startAA; i <= endAA; i++)
            {
                columns.push_back(m_parent.GetAAName((CMAA2Sample::AAType)i));
            }

            abTool.ReportStart();
            abTool.ReportAddRowValues(columns);
            m_totalTimePerAAOption.resize(columns.size());
            m_currentAAOption = 0; // 시작 옵션 인덱스 초기화
            m_currentFrame = -51;
        }

        m_currentFrame++;
        m_timer.Tick();

        // finished current AA option
        if (m_currentFrame >= c_totalFrameCount)
        {
            m_totalTimePerAAOption[m_currentAAOption + c_warmupLoops] = (float)m_timer.GetTimeFromStart();
            m_timer.Stop();

            m_currentFrame = -50;

            // 0(None) 다음에는 바로 3(SMAA)으로 점프
            if (m_currentAAOption == 0)
                m_currentAAOption = 3;
            else
                m_currentAAOption++; // 3 다음에는 4가 되어 루프 종료 조건으로 진입
        }

        // End all and write report
        // 조기종료 조건문
        if ((startAA + m_currentAAOption) > endAA)
        {
            m_isDone = true;
            assert(!m_timer.IsRunning());

            vector<string> row(m_totalTimePerAAOption.size(), "");
            row[0] = "Total time";
            for (int i = 0; i < m_totalTimePerAAOption.size() - 1; i++)
                row[i + 1] = vaStringTools::Format("%.3f", m_totalTimePerAAOption[i]);
            abTool.ReportAddRowValues(row);

            row[0] = "Avg FPS";
            for (int i = 0; i < m_totalTimePerAAOption.size() - 1; i++)
                row[i + 1] = vaStringTools::Format("%.3f", (float)c_totalFrameCount / m_totalTimePerAAOption[i]);
            abTool.ReportAddRowValues(row);

            row[0] = "Avg frame time (ms)";
            for (int i = 0; i < m_totalTimePerAAOption.size() - 1; i++)
                row[i + 1] = vaStringTools::Format("%.3f", m_totalTimePerAAOption[i] / (float)c_totalFrameCount * 1000.0f);
            abTool.ReportAddRowValues(row);

            row[0] = "Avg delta from no-AA (ms)";
            float avgNoAA = m_totalTimePerAAOption[c_warmupLoops] / (float)c_totalFrameCount * 1000.0f;
            for (int i = 0; i < c_warmupLoops + 1; i++)
                row[i + 1] = "";
            for (int i = c_warmupLoops; i < m_totalTimePerAAOption.size() - 1; i++)
                row[i + 1] = vaStringTools::Format("%.3f", (m_totalTimePerAAOption[i] / (float)c_totalFrameCount * 1000.0f) - avgNoAA);
            abTool.ReportAddRowValues(row);

            abTool.ReportFinish();
            return;
        }
        else
        {
            // 현재 옵션 할당
            // 웜업 구간이 아닐 때만 실제 범위를 순회하도록 설정
            m_parent.Settings().CurrentAAOption = (CMAA2Sample::AAType)(startAA + m_currentAAOption);
        }

        // we only start measuring after the initial 'flush' frames
        if (m_currentFrame == 0)
            m_timer.Start();

        // static images bench 추가
        if (m_parent.Settings().SceneChoice != CMAA2Sample::SceneSelectionType::StaticImage)
        {
            m_parent.GetFlythroughCameraController()->SetPlayTime(vaMath::Max(0.0f, m_currentFrame * c_frameDeltaTime));
        }
    }
    virtual void    OnRender(AutoBenchTool&) override {}
    //virtual void    OnRenderComparePoint( AutoBenchTool & abTool, vaImageCompareTool & imageCompareTool, vaRenderDeviceContext & renderContext, const shared_ptr<vaTexture> & colorInOut, shared_ptr<vaPostProcess> & postProcess ) override;
    virtual bool    IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual float   GetProgress() const override { if (m_totalTimePerAAOption.size() == 0) return 0.5f; return (float)(m_currentAAOption + c_warmupLoops + (float)m_currentFrame / (c_totalFrameCount - 1)) / (float)(m_totalTimePerAAOption.size() - 1); }
};

// 추가
class BenchItemSMAAOnly : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 30;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const int           c_warmupFrames = 50;
    const int           c_measureFrames;

    int                 m_currentFrame;
    bool                m_isDone;
    double              m_accumulatedTime;
    float               m_peakTime;

public:
    BenchItemSMAAOnly(CMAA2Sample& parent)
        : AutoBenchToolWorkItem(parent),
        m_currentFrame(-50),  // -c_warmupFrames
        m_isDone(false),
        m_accumulatedTime(0.0),
        m_peakTime(0.0f),
        c_measureFrames(
            (parent.Settings().SceneChoice == CMAA2Sample::SceneSelectionType::StaticImage)
            ? 16000
            : (int)(parent.GetFlythroughCameraController()->GetTotalTime() / (1.0f / c_framePerSecond))
        ) {
    }

protected:
    virtual void Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA;

        if (m_currentFrame == -50)
        {
            abTool.ReportStart();
            abTool.ReportAddText("SMAA-only GPU time benchmark\r\n\r\n");
        }

        m_currentFrame++;

        if (m_currentFrame <= 0) return;

        if (m_parent.Settings().SceneChoice != CMAA2Sample::SceneSelectionType::StaticImage)
            m_parent.GetFlythroughCameraController()->SetPlayTime(
                fmod((float)m_currentFrame * c_frameDeltaTime,
                    m_parent.GetFlythroughCameraController()->GetTotalTime())
            );

        float smaaMs = 0.0f;
        auto* profiler = vaProfiler::GetInstancePtr();
        if (profiler != nullptr)
        {
            const vaNestedProfilerNode* smaaNode = profiler->FindNode("SMAA");
            if (smaaNode != nullptr)
                smaaMs = (float)smaaNode->GetFrameLastTotalTimeGPU() * 1000.0f;
        }

        if (smaaMs > 0.0f)
        {
            m_accumulatedTime += smaaMs;
            m_peakTime = std::max(m_peakTime, smaaMs);
        }

        if (m_currentFrame >= c_measureFrames)
        {
            float avgMs = (float)(m_accumulatedTime / c_measureFrames);

            vector<string> header = { "Metric", "Value (ms)" };
            abTool.ReportAddRowValues(header);
            abTool.ReportAddRowValues({ "SMAA Avg",  vaStringTools::Format("%.4f", avgMs) });
            abTool.ReportAddRowValues({ "SMAA Peak", vaStringTools::Format("%.4f", m_peakTime) });
            abTool.ReportAddRowValues({ "Measured Frames", vaStringTools::Format("%d", c_measureFrames) });

            abTool.ReportFinish();
            m_isDone = true;
        }
    }

    virtual void  OnRender(AutoBenchTool&) override {}
    virtual bool  IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual float GetProgress() const override { return (float)std::max(0, m_currentFrame) / c_measureFrames; }
};

class BenchItemCompareAllToRef : public AutoBenchToolWorkItem
{
    const CMAA2Sample::AAType   m_reference1 = CMAA2Sample::AAType::SuperSampleReference;    // main test - difference from supersampled reference AA
    const CMAA2Sample::AAType   m_reference2 = CMAA2Sample::AAType::None;                    // secondary test - difference from input no AA image

    const float                 c_frameDeltaTime = 1.0f / (float)BenchItemPerformance::c_framePerSecond;
    const int                   c_totalFrameCount;
    const int                   c_totalFramesToTest = 8;
    int                         m_currentAAOption;
    int                         m_currentTestTimePoint;
    int                         m_currentReference;
    bool                        m_isDone;
    vector<string>              m_reportRowPSNR;
    vector<string>              m_reportRowMSE;
    vector<float>               m_reportAvgPSNR;
    // instead of manually settings them just spread them out over 10 locations, should be good enough
    vector<float>               m_timePointsToTest; // = { 21.5f, 45.0f, 57.0f, 71.5f, 91.5f, 111.5f, 128.0f, 145.5f };
public:
    BenchItemCompareAllToRef(CMAA2Sample& parent) : AutoBenchToolWorkItem(parent), m_currentTestTimePoint(0), m_currentAAOption(-2), m_currentReference(0), m_isDone(false),
        c_totalFrameCount((int)(parent.GetFlythroughCameraController()->GetTotalTime() / c_frameDeltaTime))
    {
        // instead of manually settings them just spread them out over c_totalFramesToTest locations, should be good enough
        if (m_timePointsToTest.size() == 0)
            for (int i = 0; i < c_totalFramesToTest; i++)
                m_timePointsToTest.push_back(c_frameDeltaTime * ((float)c_totalFrameCount * ((float)i + 0.5f) / (float)c_totalFramesToTest));
    }
protected:
    virtual void    Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;

        // 성능 측정과 동일하게 범위를 잡아줌
        const int startAA = (int)CMAA2Sample::AAType::None;
        const int endAA = (int)CMAA2Sample::AAType::SMAA;

        m_currentAAOption++;

        // 중간 단계(1, 2)를 건너뛰는 로직
        if (m_currentAAOption == 1 || m_currentAAOption == 2)
        {
            m_currentAAOption = 3;
        }

        // 전체 개수 대신 endAA 기준으로 종료 체크
        if ((startAA + m_currentAAOption) > endAA)
        {
            // 리포트 행 추가 (testList가 없으므로 인덱스 범위를 직접 씁니다)
            abTool.ReportAddRowValues(m_reportRowPSNR);
            // abTool.ReportAddRowValues(vector<string>(m_reportRowPSNR.begin(), m_reportRowPSNR.begin() + ((m_currentReference == 0) ? ((int)CMAA2Sample::AAType::SuperSampleReference + 2) : ((int)CMAA2Sample::AAType::SMAA + 2))));
            // abTool.ReportAddRowValues( m_reportRowMSE );
            // clear elements except first column which is "PSNR" / "MSE"
            for (int i = 1; i < m_reportRowPSNR.size(); i++)
                m_reportRowPSNR[i] = "";
            for (int i = 1; i < m_reportRowMSE.size(); i++)
                m_reportRowMSE[i] = "";

            m_currentAAOption = -1;
            m_currentTestTimePoint++;

            if (m_currentTestTimePoint >= m_timePointsToTest.size())
            {

                vector<string> averages;
                averages.push_back("average PSNR");
                for (int ai = 1; ai < m_reportAvgPSNR.size(); ai++)
                    averages.push_back(vaStringTools::Format("%.3f", m_reportAvgPSNR[ai] / (float)m_timePointsToTest.size()));
                abTool.ReportAddRowValues(vector<string>(averages.begin(), averages.begin() + ((m_currentReference == 0) ? ((int)CMAA2Sample::AAType::SuperSampleReference + 2) : ((int)CMAA2Sample::AAType::SMAA + 2))));
                abTool.ReportAddText("\r\n");

                if (m_currentReference == 0)
                {
                    // restart with secondary ref
                    m_currentReference = 1;
                    m_currentTestTimePoint = 0;
                    m_currentAAOption = -1;
                }
                else
                {
                    m_isDone = true;
                    abTool.ReportFinish();
                    return;
                }
            }
        }

        if (m_currentAAOption == -1)
        {
            // first capture the reference
            m_parent.Settings().CurrentAAOption = (m_currentReference == 0) ? (m_reference1) : (m_reference2);

            // initial setup
            if (m_currentTestTimePoint == 0 && m_currentReference == 0)
            {
                // various settings to ensure VISUAL determinism
                m_parent.SetRequireDeterminism(true);
                m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity();

                abTool.ReportStart();
                int count = ((int)CMAA2Sample::AAType::SuperSampleReference) + 2;
                m_reportRowPSNR.resize(count);
                //m_reportRowPSNR[0] = "PSNR";
                m_reportRowMSE.resize(count);
                //m_reportRowMSE[0] = "MSE";
                m_reportAvgPSNR.resize(count);
            }
            if (m_currentTestTimePoint == 0)
            {
                for (float& avg : m_reportAvgPSNR) avg = 0.0f;
            }

            m_parent.GetFlythroughCameraController()->SetPlayTime(m_timePointsToTest[m_currentTestTimePoint]);
            m_reportRowPSNR[0] = vaStringTools::Format("%d", m_currentTestTimePoint);
            m_reportAvgPSNR[0] = 0.0f;
            m_reportRowMSE[0] = vaStringTools::Format("%d", m_currentTestTimePoint);
        }
        else
        {
            // 옵션 할당 방식 변경
            m_parent.Settings().CurrentAAOption = (CMAA2Sample::AAType)(startAA + m_currentAAOption);
            // m_parent.Settings().CurrentAAOption = (CMAA2Sample::AAType)m_currentAAOption;
        }

        assert(m_currentTestTimePoint < m_timePointsToTest.size());
        assert(m_parent.Settings().CurrentAAOption <= CMAA2Sample::AAType::SuperSampleReference);
    }
    virtual void    OnRender(AutoBenchTool&) override {}
    virtual void    OnRenderComparePoint(AutoBenchTool& abTool, vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext, const shared_ptr<vaTexture>& colorInOut, shared_ptr<vaPostProcess>& postProcess) override
    {
        if (m_currentAAOption == -1)
        {
            imageCompareTool.SaveAsReference(renderContext, colorInOut);

            if (m_currentTestTimePoint == 0)
            {
                string info;
                if (m_currentReference == 0)
                {
                    assert(m_parent.Settings().CurrentAAOption == CMAA2Sample::AAType::SuperSampleReference);
                    int fullSampleCount = m_parent.GetSSGridRes() * m_parent.GetSSGridRes() * m_parent.GetSSResScale() * m_parent.GetSSResScale();
                    int msaaSampleCount = m_parent.GetSSMSAASampleCount();
                    info = vaStringTools::Format("reference used for PSNR: supersampled anti-aliased image at %d x %d with %d full samples each with %d MSAA samples (total %d per pixel)", colorInOut->GetSizeX(), colorInOut->GetSizeY(), fullSampleCount, msaaSampleCount, fullSampleCount * msaaSampleCount);
                    info += "\r\n(measures distance to the ideal anti-aliased image - bigger number means closer to ideal)";
                }
                else
                {
                    assert(m_parent.Settings().CurrentAAOption == CMAA2Sample::AAType::None);
                    info = "reference used for PSNR: no anti-aliasing source image";
                    info += "\r\n(measures distance to the source image - bigger number means less change to original)";
                }
                VA_LOG(info.c_str());
                abTool.ReportAddText("\r\n" + info + "\r\n");
                vector<string> columns;
                columns.push_back("");
                for (int i = 0; i <= (int)CMAA2Sample::AAType::SuperSampleReference; i++)
                    columns.push_back(m_parent.GetAAName((CMAA2Sample::AAType)i));
                assert(m_reportRowPSNR.size() == columns.size());
                abTool.ReportAddRowValues(vector<string>(columns.begin(), columns.begin() + ((m_currentReference == 0) ? ((int)CMAA2Sample::AAType::SuperSampleReference + 2) : ((int)CMAA2Sample::AAType::SMAA + 2))));
            }
        }
        else
        {
            vaVector4 diff = imageCompareTool.CompareWithReference(renderContext, colorInOut, postProcess);

            if (diff.x == -1)
            {
                m_reportRowPSNR[m_currentAAOption + 1] = "Error";
                m_reportRowMSE[m_currentAAOption + 1] = "Error";
                m_reportAvgPSNR[m_currentAAOption + 1] = std::numeric_limits<float>::infinity();
                VA_LOG_ERROR("Error: Reference image not captured, or size/format mismatch - please capture a reference image first.");
            }
            else
            {
                m_reportRowPSNR[m_currentAAOption + 1] = vaStringTools::Format("%.3f", diff.y);
                m_reportRowMSE[m_currentAAOption + 1] = vaStringTools::Format("%.7f", diff.x);
                m_reportAvgPSNR[m_currentAAOption + 1] += diff.y;
                VA_LOG_SUCCESS(" diff from reference for '%30s' : PSNR: %.3f (MSE: %f)", m_parent.GetAAName(m_parent.Settings().CurrentAAOption), diff.y, diff.x);
            }

            if (m_currentReference == 0)
                colorInOut->SaveToPNGFile(renderContext, abTool.ReportGetDir() + vaStringTools::SimpleWiden(vaStringTools::Format("%d_%d_%s.png", m_currentTestTimePoint, m_currentAAOption, m_parent.GetAAName(m_parent.Settings().CurrentAAOption))));
        }
    }

    virtual bool    IsDone(AutoBenchTool&) const override { return m_isDone; }

    virtual float   GetProgress() const override { return 0.5f; }
};

class BenchItemRecordSMAATemporalComparison : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    float               m_captureStartTime;
    int                 m_currentMode;
    int                 m_currentFrame;
    bool                m_started;
    bool                m_isDone;
    wstring             m_outputDirs[3];

public:
    BenchItemRecordSMAATemporalComparison(CMAA2Sample& parent, float startTime, int captureFrameCount, int warmupFrameCount)
        : AutoBenchToolWorkItem(parent),
        m_captureFrameCount(vaMath::Max(1, captureFrameCount)),
        m_warmupFrameCount(vaMath::Max(1, warmupFrameCount)),
        m_captureStartTime(startTime),
        m_currentMode(0),
        m_currentFrame(0),
        m_started(false),
        m_isDone(false)
    {
        const float minimumStartTime = m_warmupFrameCount * c_frameDeltaTime;
        const float maximumStartTime = vaMath::Max(minimumStartTime,
            parent.GetFlythroughCameraController()->GetTotalTime() - (m_captureFrameCount - 1) * c_frameDeltaTime);
        m_captureStartTime = vaMath::Clamp(m_captureStartTime, minimumStartTime, maximumStartTime);
    }

protected:
    virtual void Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;

        if (!m_started)
        {
            m_started = true;
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);
            m_parent.SetFixedDeltaTime(c_frameDeltaTime);
            m_parent.SetSMAAPreset(vaSMAAWrapper::Preset::PRESET_ULTRA);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity();

            abTool.ReportStart();
            m_outputDirs[0] = abTool.ReportGetDir() + L"O_SMAA_1X\\";
            m_outputDirs[1] = abTool.ReportGetDir() + L"O_T2X\\";
            m_outputDirs[2] = abTool.ReportGetDir() + L"O_T2X_R\\";
            vaFileTools::EnsureDirectoryExists(m_outputDirs[0]);
            vaFileTools::EnsureDirectoryExists(m_outputDirs[1]);
            vaFileTools::EnsureDirectoryExists(m_outputDirs[2]);

            abTool.ReportAddText("Original SMAA 1X / O-T2X / O-T2X-R temporal quality capture\r\n\r\n");
            abTool.ReportAddText(vaStringTools::Format("Frame rate:    %d FPS\r\n", c_framePerSecond));
            abTool.ReportAddText("SMAA preset:   Ultra\r\n");
            abTool.ReportAddText(vaStringTools::Format("Start time:    %.3f s\r\n", m_captureStartTime));
            abTool.ReportAddText(vaStringTools::Format("Warm-up:       %d frames\r\n", m_warmupFrameCount));
            abTool.ReportAddText(vaStringTools::Format("Capture:       %d frames per mode\r\n\r\n", m_captureFrameCount));

            m_currentMode = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        // Keep the last warm-up frame fixed until static light shadowmaps have
        // settled, so frame zero never starts with partially updated lighting.
        if (m_currentFrame == -1 && m_parent.HasPendingShadowmapUpdates())
            return;

        m_currentFrame++;
        if (m_currentFrame >= m_captureFrameCount)
        {
            m_currentMode++;
            if (m_currentMode >= 3)
            {
                m_isDone = true;
                abTool.ReportFinish();
                return;
            }
            m_currentFrame = -m_warmupFrameCount;
        }

        const CMAA2Sample::AAType modes[3] = { CMAA2Sample::AAType::SMAA, CMAA2Sample::AAType::SMAA_O_T2X, CMAA2Sample::AAType::SMAA_O_T2X_R };
        m_parent.Settings().CurrentAAOption = modes[m_currentMode];

        const float playTime = m_captureStartTime + m_currentFrame * c_frameDeltaTime;
        m_parent.GetFlythroughCameraController()->SetPlayTime(vaMath::Max(0.0f, playTime));
    }

    virtual void OnRender(AutoBenchTool&) override {}

    virtual void OnRenderComparePoint(AutoBenchTool& abTool, vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext,
        const shared_ptr<vaTexture>& colorInOut, shared_ptr<vaPostProcess>& postProcess) override
    {
        abTool; imageCompareTool; postProcess;
        if (m_currentMode < 3 && m_currentFrame >= 0 && m_currentFrame < m_captureFrameCount)
        {
            const char* modeNames[3] = { "O_SMAA_1X", "O_T2X", "O_T2X_R" };
            const char* modeName = modeNames[m_currentMode];
            const wstring fileName = m_outputDirs[m_currentMode] + vaStringTools::SimpleWiden(
                vaStringTools::Format("%s_frame_%05d.png", modeName, m_currentFrame));
            if (!colorInOut->SaveToPNGFile(renderContext, fileName))
                VA_LOG_ERROR(L"Failed to save temporal comparison frame '%s'", fileName.c_str());
        }
    }

    virtual bool IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual bool IsCapturingFrame() const override
    {
        return m_currentMode < 3 && m_currentFrame >= 0 && m_currentFrame < m_captureFrameCount;
    }

    virtual float GetProgress() const override
    {
        const int framesPerMode = m_warmupFrameCount + m_captureFrameCount;
        const int completedFrames = m_currentMode * framesPerMode + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp((float)completedFrames / (float)(framesPerMode * 3), 0.0f, 1.0f);
    }
};

class BenchItemRecordSMAATemporalMatrix : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    static const int    c_originalModeCount = 4;
    static const int    c_modeCapacity = 8;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    const int           m_modeCount;
    float               m_captureStartTime;
    int                 m_currentMode;
    int                 m_currentFrame;
    bool                m_started;
    bool                m_isDone;
    wstring             m_outputDirs[c_modeCapacity];

    static const char * GetModeID( int mode )
    {
        static const char * c_modeIDs[c_modeCapacity] =
        {
            "O-T2X", "O-T2X-R", "O-ET2X", "O-ET2X-R",
            "A-T2X", "A-T2X-R", "A-ET2X", "A-ET2X-R"
        };
        return c_modeIDs[mode];
    }

    static const char * GetModeDirectory( int mode )
    {
        static const char * c_modeDirectories[c_modeCapacity] =
        {
            "O_T2X", "O_T2X_R", "O_ET2X", "O_ET2X_R",
            "A_T2X", "A_T2X_R", "A_ET2X", "A_ET2X_R"
        };
        return c_modeDirectories[mode];
    }

    static const char * GetModeDescription( int mode )
    {
        static const char * c_modeDescriptions[c_modeCapacity] =
        {
            "Original SMAA Standard T2X",
            "Original SMAA Standard T2X + camera reprojection",
            "Original SMAA TSCMAA-inspired edge-selective temporal, no-reprojection ablation",
            "Original SMAA TSCMAA-inspired edge-selective temporal + camera reprojection",
            "Adaptive SMAA Standard T2X",
            "Adaptive SMAA Standard T2X + camera reprojection",
            "Adaptive SMAA TSCMAA-inspired edge-selective temporal, no-reprojection ablation",
            "Adaptive SMAA TSCMAA-inspired edge-selective temporal + camera reprojection"
        };
        return c_modeDescriptions[mode];
    }

    static CMAA2Sample::AAType GetModeAAType( int mode )
    {
        static const CMAA2Sample::AAType c_modes[c_modeCapacity] =
        {
            CMAA2Sample::AAType::SMAA_O_T2X,
            CMAA2Sample::AAType::SMAA_O_T2X_R,
            CMAA2Sample::AAType::SMAA_O_ET2X,
            CMAA2Sample::AAType::SMAA_O_ET2X_R,
            CMAA2Sample::AAType::SMAA_A_T2X,
            CMAA2Sample::AAType::SMAA_A_T2X_R,
            CMAA2Sample::AAType::SMAA_A_ET2X,
            CMAA2Sample::AAType::SMAA_A_ET2X_R
        };
        return c_modes[mode];
    }

public:
    BenchItemRecordSMAATemporalMatrix(CMAA2Sample& parent, float startTime, int captureFrameCount, int warmupFrameCount, bool includeAdaptive)
        : AutoBenchToolWorkItem(parent),
        m_captureFrameCount(vaMath::Max(1, captureFrameCount)),
        m_warmupFrameCount(vaMath::Max(1, warmupFrameCount)),
        m_modeCount(includeAdaptive? c_modeCapacity : c_originalModeCount),
        m_captureStartTime(startTime),
        m_currentMode(0),
        m_currentFrame(0),
        m_started(false),
        m_isDone(false)
    {
        const float minimumStartTime = m_warmupFrameCount * c_frameDeltaTime;
        const float maximumStartTime = vaMath::Max(minimumStartTime,
            parent.GetFlythroughCameraController()->GetTotalTime() - (m_captureFrameCount - 1) * c_frameDeltaTime);
        m_captureStartTime = vaMath::Clamp(m_captureStartTime, minimumStartTime, maximumStartTime);
    }

protected:
    virtual void Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;

        if (!m_started)
        {
            m_started = true;
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);
            m_parent.SetFixedDeltaTime(c_frameDeltaTime);
            m_parent.SetSMAAPreset(vaSMAAWrapper::Preset::PRESET_ULTRA);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity();

            abTool.ReportStart();
            for( int i = 0; i < m_modeCount; i++ )
            {
                m_outputDirs[i] = abTool.ReportGetDir() + vaStringTools::SimpleWiden( GetModeDirectory( i ) ) + L"\\";
                vaFileTools::EnsureDirectoryExists(m_outputDirs[i]);
            }

            abTool.ReportAddText(m_modeCount == c_modeCapacity?
                "SMAA eight-case temporal capture\r\n\r\n" :
                "Original SMAA four-mode temporal capture\r\n\r\n");
            abTool.ReportAddText("Engineering comparison capture; this is not a formal quality or performance result.\r\n");
            abTool.ReportAddText("O-T2X and O-T2X-R use the official SMAA T2X jitter pattern.\r\n");
            abTool.ReportAddText("O-ET2X and O-ET2X-R use the Intel-document-family edge-selective SMAA adaptation without deliberate projection jitter.\r\n");
            abTool.ReportAddText("O-ET2X is the no-reprojection ablation; O-ET2X-R uses camera-motion reprojection only.\r\n");
            abTool.ReportAddText("Both use IntelFamilyNonDominant candidates, Catmull-Rom 5-tap history sampling, YCoCg variance clipping, and history weight 0.8.\r\n\r\n");
            abTool.ReportAddText(vaStringTools::Format("Frame rate:    %d FPS\r\n", c_framePerSecond));
            abTool.ReportAddText("SMAA preset:   Ultra\r\n");
            abTool.ReportAddText(vaStringTools::Format("Start time:    %.3f s\r\n", m_captureStartTime));
            abTool.ReportAddText(vaStringTools::Format("Warm-up:       %d frames\r\n", m_warmupFrameCount));
            abTool.ReportAddText("Shadowmaps:    wait for stable lighting before frame zero\r\n");
            abTool.ReportAddText(vaStringTools::Format("Capture:       %d frames per mode\r\n\r\n", m_captureFrameCount));
            abTool.ReportAddRowValues({ "Mode", "AA implementation", "Output directory" });
            for( int mode = 0; mode < m_modeCount; mode++ )
                abTool.ReportAddRowValues({ GetModeID( mode ), GetModeDescription( mode ), GetModeDirectory( mode ) });

            m_currentMode = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        // Keep the last warm-up frame fixed until static light shadowmaps have
        // settled, so frame zero never starts with partially updated lighting.
        if (m_currentFrame == -1 && m_parent.HasPendingShadowmapUpdates())
            return;

        m_currentFrame++;
        if (m_currentFrame >= m_captureFrameCount)
        {
            m_currentMode++;
            if (m_currentMode >= m_modeCount)
            {
                m_isDone = true;
                abTool.ReportFinish();
                return;
            }
            m_currentFrame = -m_warmupFrameCount;
        }

        m_parent.Settings().CurrentAAOption = GetModeAAType(m_currentMode);

        const float playTime = m_captureStartTime + m_currentFrame * c_frameDeltaTime;
        m_parent.GetFlythroughCameraController()->SetPlayTime(vaMath::Max(0.0f, playTime));
    }

    virtual void OnRender(AutoBenchTool&) override {}

    virtual void OnRenderComparePoint(AutoBenchTool& abTool, vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext,
        const shared_ptr<vaTexture>& colorInOut, shared_ptr<vaPostProcess>& postProcess) override
    {
        abTool; imageCompareTool; postProcess;
        if (m_currentMode < m_modeCount && m_currentFrame >= 0 && m_currentFrame < m_captureFrameCount)
        {
            const char* modeName = GetModeDirectory(m_currentMode);
            const wstring fileName = m_outputDirs[m_currentMode] + vaStringTools::SimpleWiden(
                vaStringTools::Format("%s_frame_%05d.png", modeName, m_currentFrame));
            if (!colorInOut->SaveToPNGFile(renderContext, fileName))
                VA_LOG_ERROR(L"Failed to save SMAA temporal frame '%s'", fileName.c_str());
        }
    }

    virtual bool IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual bool IsCapturingFrame() const override
    {
        return m_currentMode < m_modeCount && m_currentFrame >= 0 && m_currentFrame < m_captureFrameCount;
    }

    virtual float GetProgress() const override
    {
        const int framesPerMode = m_warmupFrameCount + m_captureFrameCount;
        const int completedFrames = m_currentMode * framesPerMode + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp((float)completedFrames / (float)(framesPerMode * m_modeCount), 0.0f, 1.0f);
    }
};

class BenchItemRecordSMAATemporalStressMatrix : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    static const int    c_modeCapacity = 8;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const CMAA2Sample::SMAATemporalStressScenario m_scenario;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    const bool          m_oneXControlsOnly;
    const int           m_modeCount;
    int                 m_currentMode = 0;
    int                 m_currentFrame = 0;
    bool                m_started = false;
    bool                m_isDone = false;
    wstring             m_outputDirs[c_modeCapacity];

    static const char * GetModeID(int mode, bool oneXControlsOnly)
    {
        if(oneXControlsOnly)
        {
            static const char * c_controlModeIDs[2] = { "O-1X", "A-1X" };
            return c_controlModeIDs[mode];
        }
        static const char * c_modeIDs[c_modeCapacity] =
        {
            "O-T2X", "O-T2X-R", "O-ET2X", "O-ET2X-R",
            "A-T2X", "A-T2X-R", "A-ET2X", "A-ET2X-R"
        };
        return c_modeIDs[mode];
    }

    static const char * GetModeDirectory(int mode, bool oneXControlsOnly)
    {
        if(oneXControlsOnly)
        {
            static const char * c_controlModeDirectories[2] = { "O_1X", "A_1X" };
            return c_controlModeDirectories[mode];
        }
        static const char * c_modeDirectories[c_modeCapacity] =
        {
            "O_T2X", "O_T2X_R", "O_ET2X", "O_ET2X_R",
            "A_T2X", "A_T2X_R", "A_ET2X", "A_ET2X_R"
        };
        return c_modeDirectories[mode];
    }

    static CMAA2Sample::AAType GetModeAAType(int mode, bool oneXControlsOnly)
    {
        if(oneXControlsOnly)
        {
            static const CMAA2Sample::AAType c_controlModes[2] =
            {
                CMAA2Sample::AAType::SMAA,
                CMAA2Sample::AAType::SMAA_A_1X
            };
            return c_controlModes[mode];
        }
        static const CMAA2Sample::AAType c_modes[c_modeCapacity] =
        {
            CMAA2Sample::AAType::SMAA_O_T2X,
            CMAA2Sample::AAType::SMAA_O_T2X_R,
            CMAA2Sample::AAType::SMAA_O_ET2X,
            CMAA2Sample::AAType::SMAA_O_ET2X_R,
            CMAA2Sample::AAType::SMAA_A_T2X,
            CMAA2Sample::AAType::SMAA_A_T2X_R,
            CMAA2Sample::AAType::SMAA_A_ET2X,
            CMAA2Sample::AAType::SMAA_A_ET2X_R
        };
        return c_modes[mode];
    }

public:
    BenchItemRecordSMAATemporalStressMatrix(CMAA2Sample& parent,
        CMAA2Sample::SMAATemporalStressScenario scenario,
        int captureFrameCount, int warmupFrameCount,
        bool oneXControlsOnly = false)
        : AutoBenchToolWorkItem(parent),
        m_scenario(scenario),
        m_captureFrameCount(vaMath::Max(1, captureFrameCount)),
        m_warmupFrameCount(vaMath::Max(1, warmupFrameCount)),
        m_oneXControlsOnly(oneXControlsOnly),
        m_modeCount(oneXControlsOnly? 2 : c_modeCapacity)
    {
    }

protected:
    virtual void Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;

        if(!m_started)
        {
            m_started = true;
            m_parent.Settings().SceneChoice =
                CMAA2Sample::SceneSelectionType::SMAATemporalStressTest;
            m_parent.SetFlythroughCameraEnabled(false);
            m_parent.SetRequireDeterminism(true);
            m_parent.SetFixedDeltaTime(c_frameDeltaTime);
            m_parent.SetSMAAPreset(vaSMAAWrapper::Preset::PRESET_ULTRA);
            m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled(false);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity();

            abTool.ReportStart();
            for(int mode = 0; mode < m_modeCount; mode++)
            {
                m_outputDirs[mode] = abTool.ReportGetDir()
                    + vaStringTools::SimpleWiden(GetModeDirectory(mode, m_oneXControlsOnly)) + L"\\";
                vaFileTools::EnsureDirectoryExists(m_outputDirs[mode]);
            }

            abTool.ReportAddText(m_oneXControlsOnly?
                "SMAA 1X dedicated temporal stress quality controls\r\n\r\n" :
                "SMAA eight-case dedicated temporal stress capture\r\n\r\n");
            abTool.ReportAddText(vaStringTools::Format("Scenario:       %s\r\n",
                CMAA2Sample::GetSMAATemporalStressScenarioName(m_scenario)));
            abTool.ReportAddText("Scene:          procedural thin lines, moving occluder, rotating blades\r\n");
            abTool.ReportAddText("API/preset:     DirectX 11, SMAA Ultra\r\n");
            abTool.ReportAddText("Timeline:       fixed 60 Hz and identical per mode\r\n");
            abTool.ReportAddText(vaStringTools::Format("Warm-up:        %d frames\r\n",
                m_warmupFrameCount));
            abTool.ReportAddText(vaStringTools::Format("Capture:        %d frames per mode\r\n",
                m_captureFrameCount));
            abTool.ReportAddText(m_oneXControlsOnly?
                "Temporal scope: spatial-only controls; no jitter, history, or reprojection\r\n" :
                "Motion scope:   -R modes reproject camera motion only; object motion vectors are not connected\r\n");
            abTool.ReportAddText("Classification: dedicated quality evidence; PNG capture is not a performance measurement\r\n\r\n");
            abTool.ReportAddRowValues({ "Mode", "Output directory" });
            for(int mode = 0; mode < m_modeCount; mode++)
                abTool.ReportAddRowValues({
                    GetModeID(mode, m_oneXControlsOnly),
                    GetModeDirectory(mode, m_oneXControlsOnly) });

            m_currentMode = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        m_currentFrame++;
        if(m_currentFrame >= m_captureFrameCount)
        {
            m_currentMode++;
            if(m_currentMode >= m_modeCount)
            {
                m_isDone = true;
                abTool.ReportFinish();
                return;
            }
            m_currentFrame = -m_warmupFrameCount;
        }

        m_parent.Settings().CurrentAAOption =
            GetModeAAType(m_currentMode, m_oneXControlsOnly);
        m_parent.SetSMAATemporalStressTestState(
            m_scenario, (float)m_currentFrame * c_frameDeltaTime);
    }

    virtual void OnRender(AutoBenchTool&) override {}

    virtual void OnRenderComparePoint(AutoBenchTool& abTool,
        vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext,
        const shared_ptr<vaTexture>& colorInOut,
        shared_ptr<vaPostProcess>& postProcess) override
    {
        abTool; imageCompareTool; postProcess;
        if(m_currentMode < m_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount)
        {
            const char* modeName =
                GetModeDirectory(m_currentMode, m_oneXControlsOnly);
            const wstring fileName = m_outputDirs[m_currentMode]
                + vaStringTools::SimpleWiden(vaStringTools::Format(
                    "%s_%s_frame_%05d.png",
                    CMAA2Sample::GetSMAATemporalStressScenarioName(m_scenario),
                    modeName, m_currentFrame));
            if(!colorInOut->SaveToPNGFile(renderContext, fileName))
                VA_LOG_ERROR(L"Failed to save SMAA temporal stress frame '%s'",
                    fileName.c_str());
        }
    }

    virtual bool IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual bool IsCapturingFrame() const override
    {
        return m_currentMode < m_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount;
    }
    virtual float GetProgress() const override
    {
        const int framesPerMode = m_warmupFrameCount + m_captureFrameCount;
        const int completedFrames = m_currentMode * framesPerMode
            + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp((float)completedFrames
            / (float)(framesPerMode * m_modeCount), 0.0f, 1.0f);
    }
};

class BenchItemRecordSMAASupersampleStressReference : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const CMAA2Sample::SMAATemporalStressScenario m_scenario;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    int                 m_currentFrame = 0;
    bool                m_started = false;
    bool                m_isDone = false;
    wstring             m_outputDir;

public:
    BenchItemRecordSMAASupersampleStressReference(
        CMAA2Sample & parent,
        CMAA2Sample::SMAATemporalStressScenario scenario,
        int captureFrameCount,
        int warmupFrameCount )
        : AutoBenchToolWorkItem( parent ),
        m_scenario( scenario ),
        m_captureFrameCount( vaMath::Max( 1, captureFrameCount ) ),
        m_warmupFrameCount( vaMath::Max( 0, warmupFrameCount ) )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice =
                CMAA2Sample::SceneSelectionType::SMAATemporalStressTest;
            m_parent.Settings( ).CurrentAAOption =
                CMAA2Sample::AAType::SuperSampleReference;
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( c_frameDeltaTime );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity( );

            abTool.ReportStart( );
            m_outputDir = abTool.ReportGetDir( ) + L"SS_Reference\\";
            vaFileTools::EnsureDirectoryExists( m_outputDir );

            abTool.ReportAddText(
                "SMAA temporal stress supersample spatial-reference capture\r\n\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Scenario:       %s\r\n",
                CMAA2Sample::GetSMAATemporalStressScenarioName( m_scenario ) ) );
            abTool.ReportAddText(
                "Scene:          procedural thin lines, moving occluder, rotating blades\r\n" );
            abTool.ReportAddText(
                "API:            DirectX 11\r\n" );
            abTool.ReportAddText(
                "Timeline:       fixed 60 Hz and identical to SMAA stress captures\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Warm-up:        %d frames\r\n", m_warmupFrameCount ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Capture:        %d frames\r\n", m_captureFrameCount ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Reference:      %dx linear resolution, %dx%d within-frame subpixel grid, %dx MSAA\r\n",
                m_parent.GetSSResScale( ),
                m_parent.GetSSGridRes( ), m_parent.GetSSGridRes( ),
                m_parent.GetSSMSAASampleCount( ) ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Reference tune: MIP bias %.3f, sharpen %.3f, ddx/ddy bias %.3f\r\n",
                m_parent.GetSSMIPBias( ),
                m_parent.GetSSSharpen( ),
                m_parent.GetSSDDXDDYBias( ) ) );
            abTool.ReportAddText(
                "Temporal state: none; all subpixel samples share one output frame's scene state\r\n" );
            abTool.ReportAddText(
                "Classification: high-quality spatial reference proxy, not an absolute ground truth and not a performance measurement\r\n\r\n" );
            abTool.ReportAddRowValues(
                { "Mode", "Output directory" } );
            abTool.ReportAddRowValues(
                { "SS-Reference", "SS_Reference" } );

            m_currentFrame = -m_warmupFrameCount - 1;
        }

        m_currentFrame++;
        if( m_currentFrame >= m_captureFrameCount )
        {
            m_isDone = true;
            abTool.ReportFinish( );
            return;
        }

        m_parent.Settings( ).CurrentAAOption =
            CMAA2Sample::AAType::SuperSampleReference;
        m_parent.SetSMAATemporalStressTestState(
            m_scenario, (float)m_currentFrame * c_frameDeltaTime );
    }

    virtual void OnRender( AutoBenchTool & ) override {}

    virtual void OnRenderComparePoint(
        AutoBenchTool & abTool,
        vaImageCompareTool & imageCompareTool,
        vaRenderDeviceContext & renderContext,
        const shared_ptr<vaTexture> & colorInOut,
        shared_ptr<vaPostProcess> & postProcess ) override
    {
        abTool; imageCompareTool; postProcess;
        if( m_currentFrame >= 0 && m_currentFrame < m_captureFrameCount )
        {
            const wstring fileName = m_outputDir
                + vaStringTools::SimpleWiden( vaStringTools::Format(
                    "%s_SS_Reference_frame_%05d.png",
                    CMAA2Sample::GetSMAATemporalStressScenarioName( m_scenario ),
                    m_currentFrame ) );
            if( !colorInOut->SaveToPNGFile( renderContext, fileName ) )
                VA_LOG_ERROR(
                    L"Failed to save SMAA supersample stress reference frame '%s'",
                    fileName.c_str( ) );
        }
    }

    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override
    {
        return m_currentFrame >= 0 && m_currentFrame < m_captureFrameCount;
    }
    virtual float GetProgress( ) const override
    {
        return vaMath::Clamp(
            (float)(m_currentFrame + m_warmupFrameCount)
                / (float)(m_warmupFrameCount + m_captureFrameCount),
            0.0f, 1.0f );
    }
};

class BenchItemRecordSMAACameraMotion : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    static const int    c_originalModeCount = 5;
    static const int    c_dilationModeCount = 4;
    static const int    c_filteredQuarterModeCount = 6;
    static const int    c_fullModeCount = 10;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const CMAA2Sample::SceneSelectionType m_scene;
    const CMAA2Sample::SMAACameraMotionProfile m_profile;
    const int           m_firstProfileFrame;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    const bool          m_referenceOnly;
    const bool          m_includeAdaptive;
    const bool          m_temporalRetentionMatrix;
    const bool          m_currentEdgeDilationMatrix;
    const bool          m_filteredQuarterMatrix;
    const int           m_modeCount;
    int                 m_currentMode = 0;
    int                 m_currentFrame = 0;
    bool                m_started = false;
    bool                m_isDone = false;
    wstring             m_outputDirs[c_fullModeCount];

    const char * GetModeID( int mode ) const
    {
        if( m_filteredQuarterMatrix )
        {
            static const char * c_filteredQuarterModeIDs[c_filteredQuarterModeCount] =
            {
                "O-ET2X-R-Document",
                "ABL-Document-Dilate3x3-R",
                "ABL-Document-FilteredQuarter-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-Jitter-Dilate3x3-R",
                "ABL-Candidate-Jitter-FilteredQuarter-R"
            };
            return c_filteredQuarterModeIDs[mode];
        }
        if( m_currentEdgeDilationMatrix )
        {
            static const char * c_dilationModeIDs[c_dilationModeCount] =
            {
                "O-ET2X-R-Document",
                "ABL-Document-Dilate3x3-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-Jitter-Dilate3x3-R"
            };
            return c_dilationModeIDs[mode];
        }
        if( m_temporalRetentionMatrix )
        {
            static const char * c_temporalRetentionModeIDs[c_originalModeCount] =
            {
                "O-1X",
                "O-T2X-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-NoJitter-R",
                "O-ET2X-R-Document"
            };
            return c_temporalRetentionModeIDs[mode];
        }
        static const char * c_modeIDs[c_fullModeCount] =
        {
            "O-1X", "O-T2X", "O-T2X-R", "O-ET2X", "O-ET2X-R",
            "A-1X", "A-T2X", "A-T2X-R", "A-ET2X", "A-ET2X-R"
        };
        return c_modeIDs[mode];
    }

    const char * GetModeDirectory( int mode ) const
    {
        if( m_filteredQuarterMatrix )
        {
            static const char * c_filteredQuarterModeDirectories[c_filteredQuarterModeCount] =
            {
                "O_ET2X_R_Document",
                "ABL_Document_Dilate3x3_R",
                "ABL_Document_FilteredQuarter_R",
                "ABL_Candidate_Jitter_R",
                "ABL_Candidate_Jitter_Dilate3x3_R",
                "ABL_Candidate_Jitter_FilteredQuarter_R"
            };
            return c_filteredQuarterModeDirectories[mode];
        }
        if( m_currentEdgeDilationMatrix )
        {
            static const char * c_dilationModeDirectories[c_dilationModeCount] =
            {
                "O_ET2X_R_Document",
                "ABL_Document_Dilate3x3_R",
                "ABL_Candidate_Jitter_R",
                "ABL_Candidate_Jitter_Dilate3x3_R"
            };
            return c_dilationModeDirectories[mode];
        }
        if( m_temporalRetentionMatrix )
        {
            static const char * c_temporalRetentionModeDirectories[c_originalModeCount] =
            {
                "O_1X",
                "O_T2X_R",
                "ABL_Candidate_Jitter_R",
                "ABL_Candidate_NoJitter_R",
                "O_ET2X_R_Document"
            };
            return c_temporalRetentionModeDirectories[mode];
        }
        static const char * c_modeDirectories[c_fullModeCount] =
        {
            "O_1X", "O_T2X", "O_T2X_R", "O_ET2X", "O_ET2X_R",
            "A_1X", "A_T2X", "A_T2X_R", "A_ET2X", "A_ET2X_R"
        };
        return c_modeDirectories[mode];
    }

    CMAA2Sample::AAType GetModeAAType( int mode ) const
    {
        if( m_filteredQuarterMatrix )
        {
            static const CMAA2Sample::AAType c_filteredQuarterModes[c_filteredQuarterModeCount] =
            {
                CMAA2Sample::AAType::SMAA_O_ET2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3,
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER
            };
            return c_filteredQuarterModes[mode];
        }
        if( m_currentEdgeDilationMatrix )
        {
            static const CMAA2Sample::AAType c_dilationModes[c_dilationModeCount] =
            {
                CMAA2Sample::AAType::SMAA_O_ET2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3
            };
            return c_dilationModes[mode];
        }
        if( m_temporalRetentionMatrix )
        {
            static const CMAA2Sample::AAType c_temporalRetentionModes[c_originalModeCount] =
            {
                CMAA2Sample::AAType::SMAA,
                CMAA2Sample::AAType::SMAA_O_T2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER,
                CMAA2Sample::AAType::SMAA_O_ET2X_R
            };
            return c_temporalRetentionModes[mode];
        }
        static const CMAA2Sample::AAType c_modes[c_fullModeCount] =
        {
            CMAA2Sample::AAType::SMAA,
            CMAA2Sample::AAType::SMAA_O_T2X,
            CMAA2Sample::AAType::SMAA_O_T2X_R,
            CMAA2Sample::AAType::SMAA_O_ET2X,
            CMAA2Sample::AAType::SMAA_O_ET2X_R,
            CMAA2Sample::AAType::SMAA_A_1X,
            CMAA2Sample::AAType::SMAA_A_T2X,
            CMAA2Sample::AAType::SMAA_A_T2X_R,
            CMAA2Sample::AAType::SMAA_A_ET2X,
            CMAA2Sample::AAType::SMAA_A_ET2X_R
        };
        return c_modes[mode];
    }

public:
    BenchItemRecordSMAACameraMotion(
        CMAA2Sample & parent,
        CMAA2Sample::SceneSelectionType scene,
        CMAA2Sample::SMAACameraMotionProfile profile,
        int firstProfileFrame,
        int captureFrameCount,
        int warmupFrameCount,
        bool referenceOnly,
        bool includeAdaptive,
        bool temporalRetentionMatrix = false,
        bool currentEdgeDilationMatrix = false,
        bool filteredQuarterMatrix = false )
        : AutoBenchToolWorkItem( parent ),
        m_scene( scene ),
        m_profile( profile ),
        m_firstProfileFrame( vaMath::Max( 0, firstProfileFrame ) ),
        m_captureFrameCount( vaMath::Max( 1, captureFrameCount ) ),
        m_warmupFrameCount( vaMath::Max( 0, warmupFrameCount ) ),
        m_referenceOnly( referenceOnly ),
        m_includeAdaptive( includeAdaptive ),
        m_temporalRetentionMatrix( temporalRetentionMatrix ),
        m_currentEdgeDilationMatrix( currentEdgeDilationMatrix ),
        m_filteredQuarterMatrix( filteredQuarterMatrix ),
        m_modeCount( referenceOnly? 1 : (filteredQuarterMatrix?
            c_filteredQuarterModeCount : (currentEdgeDilationMatrix?
            c_dilationModeCount : (includeAdaptive? c_fullModeCount : c_originalModeCount))) )
    {
        assert( (int)referenceOnly + (int)includeAdaptive
            + (int)temporalRetentionMatrix + (int)currentEdgeDilationMatrix
            + (int)filteredQuarterMatrix <= 1 );
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice = m_scene;
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( c_frameDeltaTime );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled( false );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity( );

            abTool.ReportStart( );
            if( m_referenceOnly )
            {
                m_outputDirs[0] = abTool.ReportGetDir( ) + L"SS_Reference\\";
                vaFileTools::EnsureDirectoryExists( m_outputDirs[0] );
            }
            else
            {
                for( int mode = 0; mode < m_modeCount; mode++ )
                {
                    m_outputDirs[mode] = abTool.ReportGetDir( )
                        + vaStringTools::SimpleWiden( GetModeDirectory( mode ) ) + L"\\";
                    vaFileTools::EnsureDirectoryExists( m_outputDirs[mode] );
                }
            }

            const int profileFrameCount =
                CMAA2Sample::GetSMAACameraMotionProfileFrameCount( m_profile );
            const bool fullProfile = m_firstProfileFrame == 0
                && m_captureFrameCount == profileFrameCount;
            abTool.ReportAddText( m_referenceOnly?
                "SMAA deterministic camera-motion supersample spatial-reference capture\r\n\r\n" :
                (m_filteredQuarterMatrix?
                    "SMAA filtered-quarter candidate-expansion controlled ablation capture\r\n\r\n" :
                (m_currentEdgeDilationMatrix?
                    "SMAA current-edge 3x3 dilation controlled ablation capture\r\n\r\n" :
                (m_temporalRetentionMatrix?
                    "SMAA deterministic real-scene temporal-retention five-way capture\r\n\r\n" :
                (m_includeAdaptive?
                    "SMAA deterministic camera-motion final eight-case plus O/A 1X controls capture\r\n\r\n" :
                    "SMAA deterministic camera-motion Original five-way capture\r\n\r\n")))) );
            abTool.ReportAddText( vaStringTools::Format(
                "Scene:           %s\r\n",
                CMAA2Sample::GetSMAACameraMotionSceneName( m_scene ) ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Camera profile:  %s\r\n",
                CMAA2Sample::GetSMAACameraMotionProfileName( m_profile ) ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Profile frames:  %d total; capture [%d, %d]\r\n",
                profileFrameCount, m_firstProfileFrame,
                m_firstProfileFrame + m_captureFrameCount - 1 ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Timeline:        fixed %d Hz; 60-frame pre/post still regions in the complete profile\r\n",
                c_framePerSecond ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Warm-up:         %d frames at the first captured pose per mode\r\n",
                m_warmupFrameCount ) );
            abTool.ReportAddText( "API/preset:      DirectX 11, SMAA Ultra\r\n" );
            abTool.ReportAddText( "Motion scope:    camera motion only; object motion vectors are not connected\r\n" );
            abTool.ReportAddText( fullProfile?
                "Classification:  complete camera profile quality capture; PNG output is not a performance measurement\r\n" :
                "Classification:  engineering subset/smoke; not a formal quality or performance result\r\n" );
            if( m_referenceOnly )
            {
                abTool.ReportAddText( vaStringTools::Format(
                    "Reference:       %dx linear resolution, %dx%d within-frame subpixel grid, %dx MSAA\r\n",
                    m_parent.GetSSResScale( ), m_parent.GetSSGridRes( ),
                    m_parent.GetSSGridRes( ), m_parent.GetSSMSAASampleCount( ) ) );
                abTool.ReportAddText( "Temporal state:  none; supersample spatial-reference proxy, not absolute ground truth\r\n\r\n" );
                abTool.ReportAddRowValues( { "Mode", "Output directory" } );
                abTool.ReportAddRowValues( { "SS-Reference", "SS_Reference" } );
            }
            else
            {
                abTool.ReportAddText( m_filteredQuarterMatrix?
                    "Comparison:      Candidate-Jitter and document profile, each with expansion None, 3x3, and filtered quarter\r\n"
                    "Order control:   no-jitter document triplet first, then jitter triplet after an equal deterministic prelude\r\n"
                    "Filtered path:   exact valid-pixel 4x4 box average to ceil(width/4)xceil(height/4), R8 storage, manual half-pixel bilinear upsample, threshold >= 0.25\r\n"
                    "Purpose:         isolate the expansion method; final 8-case modes remain unchanged\r\n\r\n" :
                (m_currentEdgeDilationMatrix?
                    "Comparison:      Candidate-Jitter and document profile, each with current-edge dilation None versus 3x3\r\n"
                    "Order control:   no-jitter document pair first, then jitter pair after an equal deterministic prelude\r\n"
                    "Purpose:         isolate current-edge 3x3 dilation; final 8-case modes remain unchanged\r\n\r\n" :
                (m_temporalRetentionMatrix?
                    "Comparison:      O-1X, Standard T2X-R, candidate-only jitter On/Off, and complete document-profile O-ET2X-R\r\n"
                    "Purpose:         measure temporal retention before current-edge dilation; no dilation is enabled\r\n\r\n" :
                (m_includeAdaptive?
                    "Comparison:      O/A-1X controls plus final Original/Adaptive, Standard/Edge-selective, reprojection Off/On eight cases\r\n\r\n" :
                    "Comparison:      O-1X plus Standard/Edge-selective T2X with reprojection Off/On\r\n\r\n"))) );
                abTool.ReportAddRowValues( { "Mode", "Output directory" } );
                for( int mode = 0; mode < m_modeCount; mode++ )
                    abTool.ReportAddRowValues( { GetModeID( mode ), GetModeDirectory( mode ) } );
            }

            m_currentMode = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
            // Render one uncounted readiness frame before the measured warm-up.
            // AutoBench Tick is paused while that frame reports shader/resource
            // work, so the next Tick is the first point at which readiness is
            // known. Reset there to prevent a variable number of compilation
            // frames from changing temporal phase for the first matrix mode.
            return;
        }

        if( m_currentFrame == -m_warmupFrameCount - 1 )
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );

        // Hold the first pose while scene resources and shadow maps settle so
        // each mode starts from the same fully rendered lighting state.
        if( m_currentFrame == -1 && m_parent.HasPendingShadowmapUpdates( ) )
        {
            m_parent.SetSMAACameraMotionTestState(
                m_scene, m_profile, m_firstProfileFrame );
            return;
        }

        m_currentFrame++;
        if( m_currentFrame >= m_captureFrameCount )
        {
            m_currentMode++;
            if( m_currentMode >= m_modeCount )
            {
                m_parent.ClearSMAACameraMotionTestState( );
                m_isDone = true;
                abTool.ReportFinish( );
                return;
            }
            m_currentFrame = -m_warmupFrameCount;
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
        }

        m_parent.Settings( ).CurrentAAOption = m_referenceOnly?
            CMAA2Sample::AAType::SuperSampleReference : GetModeAAType( m_currentMode );
        const int profileFrame = m_firstProfileFrame
            + vaMath::Max( 0, m_currentFrame );
        m_parent.SetSMAACameraMotionTestState( m_scene, m_profile, profileFrame );
    }

    virtual void OnRender( AutoBenchTool & ) override {}

    virtual void OnRenderComparePoint(
        AutoBenchTool & abTool,
        vaImageCompareTool & imageCompareTool,
        vaRenderDeviceContext & renderContext,
        const shared_ptr<vaTexture> & colorInOut,
        shared_ptr<vaPostProcess> & postProcess ) override
    {
        abTool; imageCompareTool; postProcess;
        if( m_currentMode >= m_modeCount || m_currentFrame < 0
            || m_currentFrame >= m_captureFrameCount )
            return;

        const char * modeName = m_referenceOnly?
            "SS_Reference" : GetModeDirectory( m_currentMode );
        const int profileFrame = m_firstProfileFrame + m_currentFrame;
        const wstring fileName = m_outputDirs[m_currentMode]
            + vaStringTools::SimpleWiden( vaStringTools::Format(
                "%s_%s_%s_profile_%05d_frame_%05d.png",
                CMAA2Sample::GetSMAACameraMotionSceneName( m_scene ),
                CMAA2Sample::GetSMAACameraMotionProfileName( m_profile ),
                modeName, profileFrame, m_currentFrame ) );
        if( !colorInOut->SaveToPNGFile( renderContext, fileName ) )
            VA_LOG_ERROR( L"Failed to save SMAA camera-motion frame '%s'",
                fileName.c_str( ) );
    }

    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override
    {
        return m_currentMode < m_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount;
    }
    virtual float GetProgress( ) const override
    {
        const int framesPerMode = m_warmupFrameCount + m_captureFrameCount;
        const int completedFrames = m_currentMode * framesPerMode
            + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp( (float)completedFrames
            / (float)(framesPerMode * m_modeCount), 0.0f, 1.0f );
    }
};

class BenchItemPreviewSMAACameraMotion : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    const CMAA2Sample::SceneSelectionType m_scene;
    const CMAA2Sample::SMAACameraMotionProfile m_profile;
    const CMAA2Sample::AAType m_mode;
    const string        m_semanticID;
    const int           m_repeatCount;
    const int           m_profileFrameCount;
    int                 m_currentFrame = -1;
    int                 m_currentRepeat = 0;
    bool                m_started = false;
    bool                m_pacingStarted = false;
    bool                m_isDone = false;
    std::chrono::steady_clock::time_point m_nextFrameDeadline;
    std::chrono::steady_clock::time_point m_previousFrameStart;
    vector<double>      m_frameIntervals;

    double GetYawDegreesPerFrame( ) const
    {
        switch( m_profile )
        {
        case CMAA2Sample::SMAACameraMotionProfile::YawSlow360:    return 1.5;
        case CMAA2Sample::SMAACameraMotionProfile::YawFast360:    return 6.0;
        case CMAA2Sample::SMAACameraMotionProfile::YawExtreme360: return 12.0;
        case CMAA2Sample::SMAACameraMotionProfile::YawStrafeFast: return 3.0;
        default:                                                   return 0.0;
        }
    }

    void PaceNextFrame( )
    {
        using Clock = std::chrono::steady_clock;
        const Clock::duration frameDuration =
            std::chrono::duration_cast<Clock::duration>(
                std::chrono::duration<double>( 1.0 / c_framePerSecond ) );
        const Clock::time_point now = Clock::now( );
        if( !m_pacingStarted )
        {
            m_pacingStarted = true;
            m_nextFrameDeadline = now;
            m_previousFrameStart = now;
            return;
        }

        m_nextFrameDeadline += frameDuration;
        // A shader compile or OS pause must not cause a burst of catch-up
        // frames. Preserve every analytical camera step but resume the 60 Hz
        // wall-clock cadence from the current time after a large stall.
        if( now > m_nextFrameDeadline + frameDuration * 2 )
            m_nextFrameDeadline = now;
        else if( now < m_nextFrameDeadline )
            std::this_thread::sleep_until( m_nextFrameDeadline );

        const Clock::time_point frameStart = Clock::now( );
        m_frameIntervals.push_back(
            std::chrono::duration<double>( frameStart - m_previousFrameStart ).count( ) );
        m_previousFrameStart = frameStart;
    }

public:
    BenchItemPreviewSMAACameraMotion(
        CMAA2Sample & parent,
        CMAA2Sample::SceneSelectionType scene,
        CMAA2Sample::SMAACameraMotionProfile profile,
        CMAA2Sample::AAType mode,
        const string & semanticID,
        int repeatCount )
        : AutoBenchToolWorkItem( parent ),
        m_scene( scene ),
        m_profile( profile ),
        m_mode( mode ),
        m_semanticID( semanticID ),
        m_repeatCount( vaMath::Clamp( repeatCount, 1, 20 ) ),
        m_profileFrameCount(
            CMAA2Sample::GetSMAACameraMotionProfileFrameCount( profile ) )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;
        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice = m_scene;
            m_parent.Settings( ).CurrentAAOption = m_mode;
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / (float)c_framePerSecond );
            m_parent.SetVsyncForBenchmark( false );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled( false );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity( );
            m_parent.SetSMAACameraMotionTestState( m_scene, m_profile, 0 );
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );

            abTool.ReportStart( );
            abTool.ReportAddText(
                "SMAA real-time camera-motion visual preview\r\n\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Scene:           %s\r\n",
                CMAA2Sample::GetSMAACameraMotionSceneName( m_scene ) ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Camera profile:  %s\r\n",
                CMAA2Sample::GetSMAACameraMotionProfileName( m_profile ) ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Mode:            %s\r\n", m_semanticID.c_str( ) ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Timeline:        %d frames at wall-clock %d Hz, repeats=%d\r\n",
                m_profileFrameCount, c_framePerSecond, m_repeatCount ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Yaw step:        %.3f degrees/frame\r\n",
                GetYawDegreesPerFrame( ) ) );
            abTool.ReportAddText(
                "Presentation:    visible window, VSync Off, explicit wall-clock 60 Hz pacing\r\n" );
            abTool.ReportAddText(
                "Capture:         disabled; this is visual engineering preview, not a quality or performance measurement\r\n\r\n" );
            return;
        }

        // Keep the first analytical pose while scene resources and shadow maps
        // settle. Wall-clock pacing begins only after loading has completed.
        if( m_currentFrame < 0 && m_parent.HasPendingShadowmapUpdates( ) )
        {
            m_parent.SetSMAACameraMotionTestState( m_scene, m_profile, 0 );
            return;
        }

        if( m_currentFrame + 1 >= m_profileFrameCount )
        {
            m_currentRepeat++;
            if( m_currentRepeat >= m_repeatCount )
            {
                double intervalSum = 0.0;
                double intervalMin = std::numeric_limits<double>::max( );
                double intervalMax = 0.0;
                for( double interval : m_frameIntervals )
                {
                    intervalSum += interval;
                    intervalMin = vaMath::Min( intervalMin, interval );
                    intervalMax = vaMath::Max( intervalMax, interval );
                }
                const double intervalMean = m_frameIntervals.empty( )?
                    0.0 : intervalSum / (double)m_frameIntervals.size( );
                abTool.ReportAddText( vaStringTools::Format(
                    "Observed frame-start interval: mean %.3f ms, min %.3f ms, max %.3f ms (%d samples)\r\n",
                    intervalMean * 1000.0, intervalMin * 1000.0,
                    intervalMax * 1000.0, (int)m_frameIntervals.size( ) ) );
                abTool.ReportAddText(
                    "Result: preview complete; inspect the visible window or generated 60 fps MP4 for perceived smoothness.\r\n" );
                m_parent.ClearSMAACameraMotionTestState( );
                m_isDone = true;
                abTool.ReportFinish( );
                return;
            }

            m_currentFrame = -1;
            m_parent.SetSMAACameraMotionTestState( m_scene, m_profile, 0 );
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
        }

        PaceNextFrame( );
        m_currentFrame++;
        m_parent.Settings( ).CurrentAAOption = m_mode;
        m_parent.SetSMAACameraMotionTestState(
            m_scene, m_profile, m_currentFrame );
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override { return false; }
    virtual float GetProgress( ) const override
    {
        const int completed = m_currentRepeat * m_profileFrameCount
            + vaMath::Max( 0, m_currentFrame );
        return vaMath::Clamp(
            (float)completed / (float)(m_repeatCount * m_profileFrameCount),
            0.0f, 1.0f );
    }
};

class BenchItemRecordSMAACandidateOnlyAblation : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    static const int    c_modeCapacity = 7;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const CMAA2Sample::SMAATemporalStressScenario m_scenario;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    const bool          m_fullComponentMatrix;
    const bool          m_jitterIsolationMatrix;
    const bool          m_hybridResolveMatrix;
    const int           m_modeCount;
    int                 m_currentMode = 0;
    int                 m_currentFrame = 0;
    bool                m_started = false;
    bool                m_isDone = false;
    wstring             m_outputDirs[c_modeCapacity];

    const char * GetModeID(int mode) const
    {
        if(m_hybridResolveMatrix)
        {
            static const char * c_hybridModeIDs[5] =
            {
                "O-1X",
                "O-T2X-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-NoJitter-R",
                "ABL-Candidate-DeJitter-R"
            };
            return c_hybridModeIDs[mode];
        }
        if(m_jitterIsolationMatrix)
        {
            static const char * c_jitterModeIDs[4] =
            {
                "O-1X",
                "O-T2X-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-NoJitter-R"
            };
            return c_jitterModeIDs[mode];
        }
        if(m_fullComponentMatrix)
        {
            static const char * c_componentModeIDs[c_modeCapacity] =
            {
                "O-1X",
                "O-T2X-R",
                "ABL-CandidateOnly-R",
                "ABL-Candidate+Catmull-R",
                "ABL-Candidate+Catmull+Clip-R",
                "ABL-Candidate+Catmull+Clip+W0.8-R",
                "O-ET2X-R-Document"
            };
            return c_componentModeIDs[mode];
        }
        static const char * c_modeIDs[4] =
        {
            "O-1X",
            "O-T2X-R",
            "ABL-CandidateOnly-R",
            "O-ET2X-R-Document"
        };
        return c_modeIDs[mode];
    }

    const char * GetModeDirectory(int mode) const
    {
        if(m_hybridResolveMatrix)
        {
            static const char * c_hybridModeDirectories[5] =
            {
                "O_1X",
                "O_T2X_R",
                "ABL_Candidate_Jitter_R",
                "ABL_Candidate_NoJitter_R",
                "ABL_Candidate_DeJitter_R"
            };
            return c_hybridModeDirectories[mode];
        }
        if(m_jitterIsolationMatrix)
        {
            static const char * c_jitterModeDirectories[4] =
            {
                "O_1X",
                "O_T2X_R",
                "ABL_Candidate_Jitter_R",
                "ABL_Candidate_NoJitter_R"
            };
            return c_jitterModeDirectories[mode];
        }
        if(m_fullComponentMatrix)
        {
            static const char * c_componentModeDirectories[c_modeCapacity] =
            {
                "O_1X",
                "O_T2X_R",
                "ABL_CandidateOnly_R",
                "ABL_Candidate_Catmull_R",
                "ABL_Candidate_Catmull_Clip_R",
                "ABL_Candidate_Catmull_Clip_Weight08_R",
                "O_ET2X_R_Document"
            };
            return c_componentModeDirectories[mode];
        }
        static const char * c_modeDirectories[4] =
        {
            "O_1X",
            "O_T2X_R",
            "ABL_CandidateOnly_R",
            "O_ET2X_R_Document"
        };
        return c_modeDirectories[mode];
    }

    CMAA2Sample::AAType GetModeAAType(int mode) const
    {
        if(m_hybridResolveMatrix)
        {
            static const CMAA2Sample::AAType c_hybridModes[5] =
            {
                CMAA2Sample::AAType::SMAA,
                CMAA2Sample::AAType::SMAA_O_T2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE
            };
            return c_hybridModes[mode];
        }
        if(m_jitterIsolationMatrix)
        {
            static const CMAA2Sample::AAType c_jitterModes[4] =
            {
                CMAA2Sample::AAType::SMAA,
                CMAA2Sample::AAType::SMAA_O_T2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER
            };
            return c_jitterModes[mode];
        }
        if(m_fullComponentMatrix)
        {
            static const CMAA2Sample::AAType c_componentModes[c_modeCapacity] =
            {
                CMAA2Sample::AAType::SMAA,
                CMAA2Sample::AAType::SMAA_O_T2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R,
                CMAA2Sample::AAType::SMAA_O_ET2X_R
            };
            return c_componentModes[mode];
        }
        static const CMAA2Sample::AAType c_modes[4] =
        {
            CMAA2Sample::AAType::SMAA,
            CMAA2Sample::AAType::SMAA_O_T2X_R,
            CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
            CMAA2Sample::AAType::SMAA_O_ET2X_R
        };
        return c_modes[mode];
    }

public:
    BenchItemRecordSMAACandidateOnlyAblation(CMAA2Sample& parent,
        CMAA2Sample::SMAATemporalStressScenario scenario,
        int captureFrameCount, int warmupFrameCount,
        bool fullComponentMatrix = false,
        bool jitterIsolationMatrix = false,
        bool hybridResolveMatrix = false)
        : AutoBenchToolWorkItem(parent),
        m_scenario(scenario),
        m_captureFrameCount(vaMath::Max(1, captureFrameCount)),
        m_warmupFrameCount(vaMath::Max(1, warmupFrameCount)),
        m_fullComponentMatrix(fullComponentMatrix),
        m_jitterIsolationMatrix(jitterIsolationMatrix),
        m_hybridResolveMatrix(hybridResolveMatrix),
        m_modeCount(fullComponentMatrix? c_modeCapacity : (hybridResolveMatrix? 5 : 4))
    {
        assert((int)m_fullComponentMatrix + (int)m_jitterIsolationMatrix
            + (int)m_hybridResolveMatrix <= 1);
    }

protected:
    virtual void Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;

        if(!m_started)
        {
            m_started = true;
            m_parent.Settings().SceneChoice =
                CMAA2Sample::SceneSelectionType::SMAATemporalStressTest;
            m_parent.SetFlythroughCameraEnabled(false);
            m_parent.SetRequireDeterminism(true);
            m_parent.SetFixedDeltaTime(c_frameDeltaTime);
            m_parent.SetSMAAPreset(vaSMAAWrapper::Preset::PRESET_ULTRA);
            m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled(false);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity();

            abTool.ReportStart();
            for(int mode = 0; mode < m_modeCount; mode++)
            {
                m_outputDirs[mode] = abTool.ReportGetDir()
                    + vaStringTools::SimpleWiden(GetModeDirectory(mode)) + L"\\";
                vaFileTools::EnsureDirectoryExists(m_outputDirs[mode]);
            }

            abTool.ReportAddText(m_hybridResolveMatrix?
                "SMAA candidate/noncandidate hybrid resolve ablation capture\r\n\r\n" :
                (m_jitterIsolationMatrix?
                "SMAA candidate-only projection-jitter isolation capture\r\n\r\n" :
                (m_fullComponentMatrix?
                    "SMAA edge-selective temporal component ablation capture\r\n\r\n" :
                    "SMAA candidate-only controlled ablation capture\r\n\r\n")));
            abTool.ReportAddText(vaStringTools::Format("Scenario:       %s\r\n",
                CMAA2Sample::GetSMAATemporalStressScenarioName(m_scenario)));
            abTool.ReportAddText("Scene:          procedural thin lines, moving occluder, rotating blades\r\n");
            abTool.ReportAddText("API/preset:     DirectX 11, SMAA Ultra\r\n");
            abTool.ReportAddText("Timeline:       fixed 60 Hz and identical per mode\r\n");
            abTool.ReportAddText(vaStringTools::Format("Warm-up:        %d frames\r\n",
                m_warmupFrameCount));
            abTool.ReportAddText(vaStringTools::Format("Capture:        %d frames per mode\r\n",
                m_captureFrameCount));
            abTool.ReportAddText("Motion scope:   camera reprojection only; object motion vectors are not connected\r\n");
            abTool.ReportAddText("Classification: controlled component ablation; PNG capture is not a performance measurement\r\n\r\n");
            if(m_hybridResolveMatrix)
            {
                abTool.ReportAddText("ABL-Candidate-Jitter-R and ABL-Candidate-DeJitter-R both use SMAA T2X projection jitter/subsample indices, IntelFamilyNonDominant candidates, camera reprojection, bilinear history sampling, clipping Off, and history weight 0.5.\r\n");
                abTool.ReportAddText("Their only difference is the noncandidate base: the jittered current spatial image versus a full-screen bilinear inverse-jitter reconstruction. Candidate temporal resolve is unchanged.\r\n");
                abTool.ReportAddText("ABL-Candidate-NoJitter-R is retained as the prior global no-jitter control. DeJitter is an experimental hybrid ablation, not an Intel TSCMAA document requirement.\r\n\r\n");
            }
            else if(m_jitterIsolationMatrix)
            {
                abTool.ReportAddText("ABL-Candidate-Jitter-R and ABL-Candidate-NoJitter-R both use IntelFamilyNonDominant candidates, camera reprojection, bilinear history sampling, clipping Off, and history weight 0.5.\r\n");
                abTool.ReportAddText("Their only difference is deliberate SMAA T2X projection jitter On versus Off; this isolates global jitter on noncandidate pixels.\r\n\r\n");
            }
            else
            {
                abTool.ReportAddText("ABL-CandidateOnly-R is identical to O-T2X-R except that temporal resolve is restricted to IntelFamilyNonDominant edge candidates.\r\n");
                abTool.ReportAddText("Both use SMAA T2X jitter, bilinear history sampling, clipping Off, history weight 0.5, and camera reprojection.\r\n");
                if(m_fullComponentMatrix)
                    abTool.ReportAddText("Subsequent profiles cumulatively add Catmull-Rom 5-tap, YCoCg variance clipping, history weight 0.8, then disable deliberate jitter; every adjacent pair changes one component.\r\n");
                abTool.ReportAddText("O-ET2X-R-Document is the existing compound document profile and is included only as an endpoint reference.\r\n\r\n");
            }
            abTool.ReportAddRowValues({ "Mode", "Output directory" });
            for(int mode = 0; mode < m_modeCount; mode++)
                abTool.ReportAddRowValues({ GetModeID(mode), GetModeDirectory(mode) });

            m_currentMode = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        m_currentFrame++;
        if(m_currentFrame >= m_captureFrameCount)
        {
            m_currentMode++;
            if(m_currentMode >= m_modeCount)
            {
                m_isDone = true;
                abTool.ReportFinish();
                return;
            }
            m_currentFrame = -m_warmupFrameCount;
        }

        m_parent.Settings().CurrentAAOption = GetModeAAType(m_currentMode);
        m_parent.SetSMAATemporalStressTestState(
            m_scenario, (float)m_currentFrame * c_frameDeltaTime);
    }

    virtual void OnRender(AutoBenchTool&) override {}

    virtual void OnRenderComparePoint(AutoBenchTool& abTool,
        vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext,
        const shared_ptr<vaTexture>& colorInOut,
        shared_ptr<vaPostProcess>& postProcess) override
    {
        abTool; imageCompareTool; postProcess;
        if(m_currentMode < m_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount)
        {
            const char* modeName = GetModeDirectory(m_currentMode);
            const wstring fileName = m_outputDirs[m_currentMode]
                + vaStringTools::SimpleWiden(vaStringTools::Format(
                    "%s_%s_frame_%05d.png",
                    CMAA2Sample::GetSMAATemporalStressScenarioName(m_scenario),
                    modeName, m_currentFrame));
            if(!colorInOut->SaveToPNGFile(renderContext, fileName))
                VA_LOG_ERROR(L"Failed to save SMAA candidate-only ablation frame '%s'",
                    fileName.c_str());
        }
    }

    virtual bool IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual bool IsCapturingFrame() const override
    {
        return m_currentMode < m_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount;
    }
    virtual float GetProgress() const override
    {
        const int framesPerMode = m_warmupFrameCount + m_captureFrameCount;
        const int completedFrames = m_currentMode * framesPerMode
            + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp((float)completedFrames
            / (float)(framesPerMode * m_modeCount), 0.0f, 1.0f);
    }
};

class BenchItemRecordSMAACandidatePolicyJitterAblation : public AutoBenchToolWorkItem
{
    static const int    c_framePerSecond = 60;
    static const int    c_modeCount = 4;
    const float         c_frameDeltaTime = 1.0f / (float)c_framePerSecond;
    const CMAA2Sample::SMAATemporalStressScenario m_scenario;
    const int           m_captureFrameCount;
    const int           m_warmupFrameCount;
    int                 m_currentMode = 0;
    int                 m_currentFrame = 0;
    bool                m_started = false;
    bool                m_isDone = false;
    wstring             m_outputDirs[c_modeCount];

    static const char * GetModeID( int mode )
    {
        static const char * c_modeIDs[c_modeCount] =
        {
            "O-1X",
            "O-T2X-R",
            "ABL-Candidate-Intel-R",
            "ABL-Candidate-AllBase-R"
        };
        return c_modeIDs[mode];
    }

    static const char * GetModeDirectory( int mode )
    {
        static const char * c_modeDirectories[c_modeCount] =
        {
            "O_1X",
            "O_T2X_R",
            "ABL_Candidate_Intel_R",
            "ABL_Candidate_AllBase_R"
        };
        return c_modeDirectories[mode];
    }

    static CMAA2Sample::AAType GetModeAAType( int mode )
    {
        static const CMAA2Sample::AAType c_modes[c_modeCount] =
        {
            CMAA2Sample::AAType::SMAA,
            CMAA2Sample::AAType::SMAA_O_T2X_R,
            CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
            CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R
        };
        return c_modes[mode];
    }

    void SetModeCandidatePolicy( int mode )
    {
        if( mode == 2 )
            m_parent.SetSMAACandidatePolicyOverride(
                true, vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant );
        else if( mode == 3 )
            m_parent.SetSMAACandidatePolicyOverride(
                true, vaSMAAWrapper::CandidatePolicy::AllBaseEdges );
        else
            m_parent.SetSMAACandidatePolicyOverride(
                false, vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant );
    }

public:
    BenchItemRecordSMAACandidatePolicyJitterAblation(
        CMAA2Sample & parent,
        CMAA2Sample::SMAATemporalStressScenario scenario,
        int captureFrameCount,
        int warmupFrameCount )
        : AutoBenchToolWorkItem( parent ),
        m_scenario( scenario ),
        m_captureFrameCount( vaMath::Max( 1, captureFrameCount ) ),
        m_warmupFrameCount( vaMath::Max( 1, warmupFrameCount ) )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice =
                CMAA2Sample::SceneSelectionType::SMAATemporalStressTest;
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( c_frameDeltaTime );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled( false );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed =
                std::numeric_limits<float>::infinity( );

            abTool.ReportStart( );
            for( int mode = 0; mode < c_modeCount; mode++ )
            {
                m_outputDirs[mode] = abTool.ReportGetDir( )
                    + vaStringTools::SimpleWiden( GetModeDirectory( mode ) ) + L"\\";
                vaFileTools::EnsureDirectoryExists( m_outputDirs[mode] );
            }

            abTool.ReportAddText(
                "SMAA candidate-policy under T2X jitter ablation capture\r\n\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Scenario:       %s\r\n",
                CMAA2Sample::GetSMAATemporalStressScenarioName( m_scenario ) ) );
            abTool.ReportAddText(
                "Scene:          procedural thin lines, moving occluder, rotating blades\r\n" );
            abTool.ReportAddText(
                "API/preset:     DirectX 11, SMAA Ultra\r\n" );
            abTool.ReportAddText(
                "Timeline:       fixed 60 Hz and identical per mode\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Warm-up:        %d frames\r\n", m_warmupFrameCount ) );
            abTool.ReportAddText( vaStringTools::Format(
                "Capture:        %d frames per mode\r\n", m_captureFrameCount ) );
            abTool.ReportAddText(
                "Motion scope:   camera reprojection only; object motion vectors are not connected\r\n" );
            abTool.ReportAddText(
                "Classification: candidate-policy quality ablation; PNG capture is not a performance measurement\r\n\r\n" );
            abTool.ReportAddText(
                "Both candidate modes preserve O-T2X-R camera reprojection, full-screen SMAA T2X jitter/subsample pattern, bilinear history sampling, clipping Off, and history weight 0.5.\r\n" );
            abTool.ReportAddText(
                "The only difference between ABL-Candidate-Intel-R and ABL-Candidate-AllBase-R is IntelFamilyNonDominant versus AllBaseEdges candidate selection.\r\n\r\n" );
            abTool.ReportAddRowValues( { "Mode", "Candidate policy", "Output directory" } );
            abTool.ReportAddRowValues( { GetModeID( 0 ), "N/A", GetModeDirectory( 0 ) } );
            abTool.ReportAddRowValues( { GetModeID( 1 ), "FullScreen", GetModeDirectory( 1 ) } );
            abTool.ReportAddRowValues( { GetModeID( 2 ), "IntelFamilyNonDominant", GetModeDirectory( 2 ) } );
            abTool.ReportAddRowValues( { GetModeID( 3 ), "AllBaseEdges", GetModeDirectory( 3 ) } );

            m_currentMode = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        m_currentFrame++;
        if( m_currentFrame >= m_captureFrameCount )
        {
            m_currentMode++;
            if( m_currentMode >= c_modeCount )
            {
                m_parent.SetSMAACandidatePolicyOverride(
                    false, vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant );
                m_isDone = true;
                abTool.ReportFinish( );
                return;
            }
            m_currentFrame = -m_warmupFrameCount;
        }

        SetModeCandidatePolicy( m_currentMode );
        m_parent.Settings( ).CurrentAAOption = GetModeAAType( m_currentMode );
        m_parent.SetSMAATemporalStressTestState(
            m_scenario, (float)m_currentFrame * c_frameDeltaTime );
    }

    virtual void OnRender( AutoBenchTool & ) override {}

    virtual void OnRenderComparePoint(
        AutoBenchTool & abTool,
        vaImageCompareTool & imageCompareTool,
        vaRenderDeviceContext & renderContext,
        const shared_ptr<vaTexture> & colorInOut,
        shared_ptr<vaPostProcess> & postProcess ) override
    {
        abTool; imageCompareTool; postProcess;
        if( m_currentMode < c_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount )
        {
            const char * modeName = GetModeDirectory( m_currentMode );
            const wstring fileName = m_outputDirs[m_currentMode]
                + vaStringTools::SimpleWiden( vaStringTools::Format(
                    "%s_%s_frame_%05d.png",
                    CMAA2Sample::GetSMAATemporalStressScenarioName( m_scenario ),
                    modeName, m_currentFrame ) );
            if( !colorInOut->SaveToPNGFile( renderContext, fileName ) )
                VA_LOG_ERROR(
                    L"Failed to save SMAA candidate-policy jitter ablation frame '%s'",
                    fileName.c_str( ) );
        }
    }

    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override
    {
        return m_currentMode < c_modeCount && m_currentFrame >= 0
            && m_currentFrame < m_captureFrameCount;
    }
    virtual float GetProgress( ) const override
    {
        const int framesPerMode = m_warmupFrameCount + m_captureFrameCount;
        const int completedFrames = m_currentMode * framesPerMode
            + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp(
            (float)completedFrames / (float)(framesPerMode * c_modeCount),
            0.0f, 1.0f );
    }
};

class BenchItemSMAATemporalPerformanceBenchmark : public AutoBenchToolWorkItem
{
    static const int c_originalModeCount = 4;
    static const int c_modeCapacity = 8;
    static const int c_framePerSecond = 60;

    enum Metric
    {
        ApplicationFrameWall,
        WholeFrame,
        SMAATotal,
        GenerateCameraVelocity,
        StandardSpatialT2X,
        StandardTemporalResolve,
        SpatialSMAA1X,
        CopySpatialToHistory,
        PrepareCandidates,
        ExtractCandidates,
        DilateCandidates3x3,
        FilteredQuarterDownsample,
        FilteredQuarterUpsample,
        ComputeDispatchArgs,
        ResolveCandidates,
        OutputCopy,
        MetricCount
    };

    struct Summary
    {
        int Count = 0;
        double Mean = 0.0;
        double Median = 0.0;
        double StandardDeviation = 0.0;
        double P95 = 0.0;
        double P99 = 0.0;
        double Maximum = 0.0;
    };

    const float m_startTime;
    const int m_warmupFrameCount;
    const int m_measureFrameCount;
    const int m_repeatCount;
    const bool m_candidateAblation;
    const bool m_fullComponentAblation;
    const bool m_currentEdgeDilationAblation;
    const bool m_filteredQuarterAblation;
    const int m_modeCount;
    const float m_frameDeltaTime = 1.0f / (float)c_framePerSecond;

    vector<double> m_samples[c_modeCapacity][MetricCount];
    vector<double> m_currentRunSamples[MetricCount];
    vector<double> m_runMeans[c_modeCapacity][MetricCount];
    vector<double> m_baseEdgeCounts[c_modeCapacity];
    vector<double> m_candidateCounts[c_modeCapacity];
    vector<double> m_processCounts[c_modeCapacity];
    vaSystemTimer m_wallTimer;
    int m_currentRepeat = 0;
    int m_currentOrderIndex = 0;
    int m_currentMode = 0;
    int m_currentFrame = 0;
    bool m_started = false;
    bool m_isDone = false;
    bool m_previousFrameAvailable = false;
    bool m_passed = true;
    bool m_candidateReadbackEnabled = true;

    const char * GetModeID( int mode ) const
    {
        if( m_filteredQuarterAblation )
        {
            static const char * c_filteredQuarterModeIDs[6] =
            {
                "O-ET2X-R-Document",
                "ABL-Document-Dilate3x3-R",
                "ABL-Document-FilteredQuarter-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-Jitter-Dilate3x3-R",
                "ABL-Candidate-Jitter-FilteredQuarter-R"
            };
            return c_filteredQuarterModeIDs[mode];
        }
        if( m_currentEdgeDilationAblation )
        {
            static const char * c_dilationModeIDs[4] =
            {
                "O-ET2X-R-Document",
                "ABL-Document-Dilate3x3-R",
                "ABL-Candidate-Jitter-R",
                "ABL-Candidate-Jitter-Dilate3x3-R"
            };
            return c_dilationModeIDs[mode];
        }
        if( m_candidateAblation )
        {
            if( m_fullComponentAblation )
            {
                static const char * c_componentModeIDs[6] =
                {
                    "O-T2X-R",
                    "ABL-CandidateOnly-R",
                    "ABL-Candidate+Catmull-R",
                    "ABL-Candidate+Catmull+Clip-R",
                    "ABL-Candidate+Catmull+Clip+W0.8-R",
                    "O-ET2X-R-Document"
                };
                return c_componentModeIDs[mode];
            }
            static const char * c_ablationModeIDs[3] =
            {
                "O-T2X-R",
                "ABL-CandidateOnly-R",
                "O-ET2X-R-Document"
            };
            return c_ablationModeIDs[mode];
        }
        static const char * c_modeIDs[c_modeCapacity] =
        {
            "O-T2X", "O-T2X-R", "O-ET2X", "O-ET2X-R",
            "A-T2X", "A-T2X-R", "A-ET2X", "A-ET2X-R"
        };
        return c_modeIDs[mode];
    }

    CMAA2Sample::AAType GetModeAAType( int mode ) const
    {
        if( m_filteredQuarterAblation )
        {
            static const CMAA2Sample::AAType c_filteredQuarterModes[6] =
            {
                CMAA2Sample::AAType::SMAA_O_ET2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3,
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER
            };
            return c_filteredQuarterModes[mode];
        }
        if( m_currentEdgeDilationAblation )
        {
            static const CMAA2Sample::AAType c_dilationModes[4] =
            {
                CMAA2Sample::AAType::SMAA_O_ET2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3
            };
            return c_dilationModes[mode];
        }
        if( m_candidateAblation )
        {
            if( m_fullComponentAblation )
            {
                static const CMAA2Sample::AAType c_componentModes[6] =
                {
                    CMAA2Sample::AAType::SMAA_O_T2X_R,
                    CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                    CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R,
                    CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R,
                    CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R,
                    CMAA2Sample::AAType::SMAA_O_ET2X_R
                };
                return c_componentModes[mode];
            }
            static const CMAA2Sample::AAType c_ablationModes[3] =
            {
                CMAA2Sample::AAType::SMAA_O_T2X_R,
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R,
                CMAA2Sample::AAType::SMAA_O_ET2X_R
            };
            return c_ablationModes[mode];
        }
        static const CMAA2Sample::AAType c_modes[c_modeCapacity] =
        {
            CMAA2Sample::AAType::SMAA_O_T2X,
            CMAA2Sample::AAType::SMAA_O_T2X_R,
            CMAA2Sample::AAType::SMAA_O_ET2X,
            CMAA2Sample::AAType::SMAA_O_ET2X_R,
            CMAA2Sample::AAType::SMAA_A_T2X,
            CMAA2Sample::AAType::SMAA_A_T2X_R,
            CMAA2Sample::AAType::SMAA_A_ET2X,
            CMAA2Sample::AAType::SMAA_A_ET2X_R
        };
        return c_modes[mode];
    }

    bool IsEdgeSelectiveMode( int mode ) const
    {
        if( m_filteredQuarterAblation )
            return true;
        if( m_currentEdgeDilationAblation )
            return true;
        if( m_candidateAblation )
            return mode >= 1;
        const int temporalProfile = mode % c_originalModeCount;
        return temporalProfile == 2 || temporalProfile == 3;
    }

    static const char * GetMetricNodeName( Metric metric )
    {
        switch( metric )
        {
        case ApplicationFrameWall:      return "ApplicationFrameWall";
        case WholeFrame:                return "WholeFrame";
        case SMAATotal:                 return "SMAA";
        case GenerateCameraVelocity:    return "SMAAGenerateCameraVelocity";
        case StandardSpatialT2X:        return "SMAAStandardSpatialT2X";
        case StandardTemporalResolve:   return "SMAAStandardTemporalResolve";
        case SpatialSMAA1X:             return "SMAASpatial1X";
        case CopySpatialToHistory:      return "TSCMAACopySpatialToHistory";
        case PrepareCandidates:         return "TSCMAAPrepareCandidates";
        case ExtractCandidates:         return "TSCMAAExtractCandidates";
        case DilateCandidates3x3:       return "TSCMAADilateCandidates3x3";
        case FilteredQuarterDownsample: return "TSCMAAFilteredQuarterDownsample";
        case FilteredQuarterUpsample:   return "TSCMAAFilteredQuarterUpsample";
        case ComputeDispatchArgs:       return "TSCMAAComputeDispatchArgs";
        case ResolveCandidates:         return "TSCMAAResolveCandidates";
        case OutputCopy:                return "TSCMAAOutputCopy";
        default:                        return "Unknown";
        }
    }

    bool IsMetricExpected( int mode, Metric metric ) const
    {
        if( metric == ApplicationFrameWall || metric == WholeFrame || metric == SMAATotal )
            return true;

        if( m_currentEdgeDilationAblation || m_filteredQuarterAblation )
        {
            if( metric == GenerateCameraVelocity || metric == SpatialSMAA1X
                || metric == CopySpatialToHistory || metric == PrepareCandidates
                || metric == ExtractCandidates || metric == ComputeDispatchArgs
                || metric == ResolveCandidates || metric == OutputCopy )
                return true;
            if( metric == DilateCandidates3x3 )
                return m_filteredQuarterAblation? mode == 1 || mode == 4 : mode == 1 || mode == 3;
            if( metric == FilteredQuarterDownsample || metric == FilteredQuarterUpsample )
                return m_filteredQuarterAblation && (mode == 2 || mode == 5);
            return false;
        }

        const int temporalProfile = mode % c_originalModeCount;
        const bool standard = m_candidateAblation? mode == 0 :
            temporalProfile == 0 || temporalProfile == 1;
        const bool edgeSelective = m_candidateAblation? mode >= 1 :
            temporalProfile == 2 || temporalProfile == 3;
        const bool reprojected = m_candidateAblation? true :
            temporalProfile == 1 || temporalProfile == 3;

        if( metric == GenerateCameraVelocity )
            return reprojected;
        if( metric == StandardSpatialT2X || metric == StandardTemporalResolve )
            return standard;
        if( metric == SpatialSMAA1X || metric == CopySpatialToHistory || metric == PrepareCandidates
            || metric == ExtractCandidates || metric == ComputeDispatchArgs || metric == ResolveCandidates
            || metric == OutputCopy )
            return edgeSelective;
        if( metric == DilateCandidates3x3 )
            return false;
        if( metric == FilteredQuarterDownsample || metric == FilteredQuarterUpsample )
            return false;
        return false;
    }

    static Summary ComputeSummary( const vector<double> & values )
    {
        Summary result;
        result.Count = (int)values.size( );
        if( values.empty( ) )
            return result;

        vector<double> sorted = values;
        std::sort( sorted.begin( ), sorted.end( ) );
        for( double value : sorted )
            result.Mean += value;
        result.Mean /= (double)sorted.size( );

        const size_t middle = sorted.size( ) / 2;
        result.Median = (sorted.size( ) % 2 == 0)?
            (sorted[middle - 1] + sorted[middle]) * 0.5 : sorted[middle];

        double variance = 0.0;
        for( double value : sorted )
        {
            const double difference = value - result.Mean;
            variance += difference * difference;
        }
        result.StandardDeviation = std::sqrt( variance / (double)sorted.size( ) );

        const size_t p95Index = vaMath::Min( sorted.size( ) - 1,
            (size_t)std::ceil( 0.95 * (double)sorted.size( ) ) - 1 );
        result.P95 = sorted[p95Index];
        const size_t p99Index = vaMath::Min( sorted.size( ) - 1,
            (size_t)std::ceil( 0.99 * (double)sorted.size( ) ) - 1 );
        result.P99 = sorted[p99Index];
        result.Maximum = sorted.back( );

        return result;
    }

    int GetModeForOrder( int repeat, int orderIndex ) const
    {
        return (repeat & 1) == 0? orderIndex : m_modeCount - 1 - orderIndex;
    }

    void CollectPreviousFrame( double wallFrameMilliseconds )
    {
        vaProfiler * profiler = vaProfiler::GetInstancePtr( );
        if( profiler == nullptr )
        {
            m_passed = false;
            return;
        }

        for( int metricIndex = 0; metricIndex < MetricCount; metricIndex++ )
        {
            const Metric metric = (Metric)metricIndex;
            if( !IsMetricExpected( m_currentMode, metric ) )
                continue;

            double milliseconds = wallFrameMilliseconds;
            if( metric != ApplicationFrameWall )
            {
                const vaNestedProfilerNode * node = profiler->FindNode( GetMetricNodeName( metric ) );
                if( node == nullptr )
                {
                    m_passed = false;
                    continue;
                }
                milliseconds = node->GetFrameLastTotalTimeGPU( ) * 1000.0;
            }

            if( std::isfinite( milliseconds ) && milliseconds > 0.0 )
            {
                m_samples[m_currentMode][metricIndex].push_back( milliseconds );
                m_currentRunSamples[metricIndex].push_back( milliseconds );
            }
            else
                m_passed = false;
        }

        if( IsEdgeSelectiveMode( m_currentMode ) && m_candidateReadbackEnabled )
        {
            const vaSMAAWrapper::TemporalCandidateStatistics & statistics =
                m_parent.GetSMAATemporalCandidateStatistics( );
            if( statistics.Valid )
            {
                m_baseEdgeCounts[m_currentMode].push_back( (double)statistics.BaseEdgeCount );
                m_candidateCounts[m_currentMode].push_back( (double)statistics.CandidateCount );
                m_processCounts[m_currentMode].push_back( (double)statistics.ProcessCount );
            }
        }
    }

    void FinishCurrentRun( )
    {
        for( int metricIndex = 0; metricIndex < MetricCount; metricIndex++ )
        {
            const Metric metric = (Metric)metricIndex;
            if( !IsMetricExpected( m_currentMode, metric ) )
                continue;
            const Summary summary = ComputeSummary( m_currentRunSamples[metricIndex] );
            if( summary.Count != m_measureFrameCount )
                m_passed = false;
            else
                m_runMeans[m_currentMode][metricIndex].push_back( summary.Mean );
            m_currentRunSamples[metricIndex].clear( );
        }
    }

    void FinishReport( AutoBenchTool & abTool )
    {
        abTool.ReportAddRowValues( { "Mode", "Timing metric", "Type", "Samples", "Mean ms", "Median ms",
            "Frame stddev ms", "P95 ms", "P99 ms", "Max ms", "Runs", "Run-mean stddev ms" } );

        for( int mode = 0; mode < m_modeCount; mode++ )
        {
            for( int metricIndex = 0; metricIndex < MetricCount; metricIndex++ )
            {
                const Metric metric = (Metric)metricIndex;
                if( !IsMetricExpected( mode, metric ) )
                    continue;

                const Summary summary = ComputeSummary( m_samples[mode][metricIndex] );
                const Summary runSummary = ComputeSummary( m_runMeans[mode][metricIndex] );
                if( summary.Count != m_measureFrameCount * m_repeatCount || runSummary.Count != m_repeatCount )
                    m_passed = false;

                abTool.ReportAddRowValues( {
                    GetModeID( mode ),
                    GetMetricNodeName( metric ),
                    metric == ApplicationFrameWall? "CPU wall interval" : "GPU timestamp",
                    vaStringTools::Format( "%d", summary.Count ),
                    vaStringTools::Format( "%.6f", summary.Mean ),
                    vaStringTools::Format( "%.6f", summary.Median ),
                    vaStringTools::Format( "%.6f", summary.StandardDeviation ),
                    vaStringTools::Format( "%.6f", summary.P95 ),
                    vaStringTools::Format( "%.6f", summary.P99 ),
                    vaStringTools::Format( "%.6f", summary.Maximum ),
                    vaStringTools::Format( "%d", runSummary.Count ),
                    vaStringTools::Format( "%.6f", runSummary.StandardDeviation )
                } );
            }
        }

        abTool.ReportAddText( "\r\nFrame-rate characterization:\r\n" );
        abTool.ReportAddRowValues( { "Mode", "Wall average FPS", "Wall 1% low FPS",
            "GPU-equivalent average FPS", "GPU-equivalent 1% low FPS" } );
        for( int mode = 0; mode < m_modeCount; mode++ )
        {
            const Summary wall = ComputeSummary( m_samples[mode][ApplicationFrameWall] );
            const Summary wholeFrame = ComputeSummary( m_samples[mode][WholeFrame] );
            abTool.ReportAddRowValues( {
                GetModeID( mode ),
                vaStringTools::Format( "%.3f", wall.Mean > 0.0? 1000.0 / wall.Mean : 0.0 ),
                vaStringTools::Format( "%.3f", wall.P99 > 0.0? 1000.0 / wall.P99 : 0.0 ),
                vaStringTools::Format( "%.3f", wholeFrame.Mean > 0.0? 1000.0 / wholeFrame.Mean : 0.0 ),
                vaStringTools::Format( "%.3f", wholeFrame.P99 > 0.0? 1000.0 / wholeFrame.P99 : 0.0 )
            } );
        }

        if( m_candidateReadbackEnabled )
        {
            abTool.ReportAddText( "\r\nCandidate counter characterization (asynchronous diagnostic readback enabled):\r\n" );
            abTool.ReportAddRowValues( { "Mode", "Counter samples", "Mean base edges", "Mean candidates",
                "Mean process count", "Mean candidate/base" } );
            for( int mode = 0; mode < m_modeCount; mode++ )
            {
                if( !IsEdgeSelectiveMode( mode ) )
                    continue;
                const Summary base = ComputeSummary( m_baseEdgeCounts[mode] );
                const Summary candidates = ComputeSummary( m_candidateCounts[mode] );
                const Summary process = ComputeSummary( m_processCounts[mode] );
                const double ratio = base.Mean > 0.0? candidates.Mean / base.Mean : 0.0;
                if( base.Count == 0 || candidates.Count != base.Count || process.Count != base.Count )
                    m_passed = false;
                abTool.ReportAddRowValues( {
                    GetModeID( mode ),
                    vaStringTools::Format( "%d", base.Count ),
                    vaStringTools::Format( "%.3f", base.Mean ),
                    vaStringTools::Format( "%.3f", candidates.Mean ),
                    vaStringTools::Format( "%.3f", process.Mean ),
                    vaStringTools::Format( "%.6f", ratio )
                } );
            }
        }
        else
            abTool.ReportAddText( "\r\nCandidate counter readback was disabled for uncontaminated timing.\r\n" );

        abTool.ReportAddText( m_passed?
            "\r\nPerformance benchmark validation: PASS\r\n" :
            "\r\nPerformance benchmark validation: FAIL\r\n" );
        abTool.ReportFinish( );
        VA_LOG( "SMAA %d-mode performance benchmark: repeats=%d, warmup=%d, measured=%d per run => %s",
            m_modeCount, m_repeatCount, m_warmupFrameCount, m_measureFrameCount, m_passed? "PASS" : "FAIL" );
    }

public:
    BenchItemSMAATemporalPerformanceBenchmark( CMAA2Sample & parent, float startTime,
        int warmupFrameCount, int measureFrameCount, int repeatCount, bool includeAdaptive,
        bool candidateAblation = false, bool fullComponentAblation = false,
        bool currentEdgeDilationAblation = false, bool filteredQuarterAblation = false )
        : AutoBenchToolWorkItem( parent ),
        m_startTime( vaMath::Max( 0.0f, startTime ) ),
        m_warmupFrameCount( vaMath::Max( 8, warmupFrameCount ) ),
        m_measureFrameCount( vaMath::Max( 16, measureFrameCount ) ),
        m_repeatCount( vaMath::Clamp( repeatCount, 1, 9 ) ),
        m_candidateAblation( candidateAblation ),
        m_fullComponentAblation( fullComponentAblation ),
        m_currentEdgeDilationAblation( currentEdgeDilationAblation ),
        m_filteredQuarterAblation( filteredQuarterAblation ),
        m_modeCount( filteredQuarterAblation? 6 : (currentEdgeDilationAblation? 4 :
            (candidateAblation? (fullComponentAblation? 6 : 3) :
            (includeAdaptive? c_modeCapacity : c_originalModeCount))) )
    {
        assert( (int)candidateAblation + (int)currentEdgeDilationAblation
            + (int)filteredQuarterAblation <= 1 );
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( m_frameDeltaTime );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetVsyncForBenchmark( false );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity( );
            m_candidateReadbackEnabled = m_parent.GetSMAATemporalCandidateStatisticsReadbackEnabled( );
            vaUIManager::GetInstance( ).SetVisible( false );
            m_wallTimer.Start( );
            m_wallTimer.Tick( );

            abTool.ReportStart( );
            if( m_filteredQuarterAblation )
            {
                abTool.ReportAddText( m_repeatCount > 1?
                    "SMAA filtered-quarter candidate-expansion repeated performance benchmark\r\n\r\n" :
                    "SMAA filtered-quarter candidate-expansion GPU performance smoke\r\n\r\n" );
                abTool.ReportAddText(
                    "This compares Candidate-Jitter and the document profile, each with expansion None, 3x3, and filtered quarter.\r\n"
                    "The filtered path reports raw extraction, quarter downsample, bilinear upsample/compact, indirect resolve, and total SMAA GPU timestamps separately.\r\n" );
            }
            else if( m_currentEdgeDilationAblation )
            {
                abTool.ReportAddText( m_repeatCount > 1?
                    "SMAA current-edge 3x3 dilation repeated performance benchmark\r\n\r\n" :
                    "SMAA current-edge 3x3 dilation GPU performance smoke\r\n\r\n" );
                abTool.ReportAddText(
                    "This compares Candidate-Jitter and the document profile, each with current-edge dilation None versus 3x3.\r\n"
                    "The two-pass 3x3 path reports raw extraction, dilation, indirect dispatch, resolve, and total SMAA GPU timestamps separately.\r\n" );
            }
            else if( m_candidateAblation )
            {
                abTool.ReportAddText( m_fullComponentAblation?
                    (m_repeatCount > 1? "SMAA temporal component ablation repeated performance benchmark\r\n\r\n" :
                        "SMAA temporal component ablation GPU performance smoke\r\n\r\n") :
                    (m_repeatCount > 1? "SMAA candidate-only controlled repeated performance benchmark\r\n\r\n" :
                        "SMAA candidate-only controlled GPU performance smoke\r\n\r\n") );
                abTool.ReportAddText( m_fullComponentAblation?
                    "This cumulatively compares candidate coverage, Catmull-Rom 5-tap, YCoCg variance clipping, history weight 0.8, and the final no-jitter document endpoint.\r\n" :
                    "This compares O-T2X-R, the candidate-only controlled ablation, and the existing compound O-ET2X-R document endpoint.\r\n" );
            }
            else
            {
                abTool.ReportAddText( m_modeCount == c_modeCapacity?
                    (m_repeatCount > 1? "SMAA eight-case repeated performance benchmark\r\n\r\n" :
                        "SMAA eight-case GPU performance smoke\r\n\r\n") :
                    (m_repeatCount > 1? "Original SMAA four-mode repeated performance benchmark\r\n\r\n" :
                        "Original SMAA four-mode GPU performance smoke\r\n\r\n") );
                abTool.ReportAddText( m_modeCount == c_modeCapacity?
                    "This measures the full Original/Adaptive, Standard/Edge-selective, reprojection Off/On matrix.\r\n" :
                    "This measures the Original four cases only; it is not the final Adaptive-inclusive 8-case benchmark.\r\n" );
            }
            if( m_candidateAblation )
            {
                abTool.ReportAddText( "O-T2X-R and ABL-CandidateOnly-R keep camera reprojection, SMAA T2X jitter/subsample pattern, bilinear history sampling, clipping Off, and history weight 0.5 identical; only temporal coverage changes.\r\n" );
                if( m_fullComponentAblation )
                    abTool.ReportAddText( "Each subsequent adjacent profile changes exactly one factor: Catmull-Rom, YCoCg clipping, history weight 0.8, then deliberate jitter Off.\r\n" );
            }
            abTool.ReportAddText( "Release x64, DirectX 11, SMAA Ultra, VSync Off, fixed 60 Hz camera path, UI hidden, no PNG capture.\r\n" );
            abTool.ReportAddText( "GPU pass timings use the built-in timestamp-query profiler; values are milliseconds.\r\n" );
            abTool.ReportAddText( "WholeFrame covers GPU work between BeginFrame and EndAndPresentFrame, excluding Present itself.\r\n" );
            abTool.ReportAddText( "ApplicationFrameWall is the observed CPU wall interval between corresponding AutoBench ticks and includes Present/OS scheduling.\r\n" );
            abTool.ReportAddText( "1% low FPS is computed as 1000 / p99 frame time.\r\n" );
            abTool.ReportAddText( "Repeat traversal alternates forward and reverse mode order to reduce order bias.\r\n" );
            abTool.ReportAddText( m_candidateReadbackEnabled?
                "Candidate counter readback: enabled and reported explicitly.\r\n" :
                "Candidate counter readback: disabled for timing isolation.\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Start time: %.3f s, repeats: %d, warm-up: %d frames, measurement: %d frames per mode per repeat.\r\n\r\n",
                m_startTime, m_repeatCount, m_warmupFrameCount, m_measureFrameCount ) );

            m_currentRepeat = 0;
            m_currentOrderIndex = 0;
            m_currentMode = GetModeForOrder( m_currentRepeat, m_currentOrderIndex );
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        m_wallTimer.Tick( );
        if( m_previousFrameAvailable && m_currentFrame >= 0 )
            CollectPreviousFrame( m_wallTimer.GetDeltaTime( ) * 1000.0 );

        if( m_currentFrame == -1 && m_parent.HasPendingShadowmapUpdates( ) )
            return;

        if( m_previousFrameAvailable && m_currentFrame >= m_measureFrameCount - 1 )
        {
            FinishCurrentRun( );
            VA_LOG( "SMAA performance benchmark: repeat %d/%d completed %s (%d measured frames)",
                m_currentRepeat + 1, m_repeatCount, GetModeID( m_currentMode ), m_measureFrameCount );
            m_currentOrderIndex++;
            if( m_currentOrderIndex >= m_modeCount )
            {
                m_currentOrderIndex = 0;
                m_currentRepeat++;
                if( m_currentRepeat >= m_repeatCount )
                {
                    FinishReport( abTool );
                    m_isDone = true;
                    return;
                }
            }
            m_currentMode = GetModeForOrder( m_currentRepeat, m_currentOrderIndex );
            m_currentFrame = -m_warmupFrameCount - 1;
            m_previousFrameAvailable = false;
        }

        m_currentFrame++;
        m_parent.Settings( ).CurrentAAOption = GetModeAAType( m_currentMode );
        const float playTime = m_startTime + m_currentFrame * m_frameDeltaTime;
        m_parent.GetFlythroughCameraController( )->SetPlayTime( vaMath::Max( 0.0f, playTime ) );
        m_previousFrameAvailable = true;
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override { return false; }
    virtual float GetProgress( ) const override
    {
        const int framesPerMode = m_warmupFrameCount + m_measureFrameCount;
        const int completedProfiles = m_currentRepeat * m_modeCount + m_currentOrderIndex;
        const int completedFrames = completedProfiles * framesPerMode + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp( (float)completedFrames /
            (float)(framesPerMode * m_modeCount * m_repeatCount), 0.0f, 1.0f );
    }
};

class BenchItemSMAACandidateReadbackOverhead : public AutoBenchToolWorkItem
{
    static const int c_profileCount = 4;
    static const int c_framePerSecond = 60;

    struct Summary
    {
        int Count = 0;
        double Mean = 0.0;
        double Median = 0.0;
        double StandardDeviation = 0.0;
        double P95 = 0.0;
        double Maximum = 0.0;
    };

    const float m_startTime;
    const int m_warmupFrameCount;
    const int m_measureFrameCount;
    const float m_frameDeltaTime = 1.0f / (float)c_framePerSecond;

    vector<double> m_gpuSamples[c_profileCount];
    vector<double> m_cpuSamples[c_profileCount];
    vector<double> m_candidateCounts[c_profileCount];
    int m_currentProfile = 0;
    int m_currentFrame = 0;
    int m_disabledReadbackUnexpectedValidCount = 0;
    bool m_started = false;
    bool m_isDone = false;
    bool m_previousFrameAvailable = false;
    bool m_passed = true;

    static bool IsReprojected( int profile ) { return profile >= 2; }
    static bool IsReadbackEnabled( int profile ) { return (profile & 1) != 0; }

    static const char * GetProfileID( int profile )
    {
        static const char * c_profileIDs[c_profileCount] =
        {
            "O-ET2X / readback Off",
            "O-ET2X / readback On",
            "O-ET2X-R / readback Off",
            "O-ET2X-R / readback On"
        };
        return c_profileIDs[profile];
    }

    static CMAA2Sample::AAType GetProfileAAType( int profile )
    {
        return IsReprojected( profile )?
            CMAA2Sample::AAType::SMAA_O_ET2X_R :
            CMAA2Sample::AAType::SMAA_O_ET2X;
    }

    static Summary ComputeSummary( const vector<double> & values )
    {
        Summary result;
        result.Count = (int)values.size( );
        if( values.empty( ) )
            return result;

        vector<double> sorted = values;
        std::sort( sorted.begin( ), sorted.end( ) );
        for( double value : sorted )
            result.Mean += value;
        result.Mean /= (double)sorted.size( );

        const size_t middle = sorted.size( ) / 2;
        result.Median = (sorted.size( ) % 2 == 0)?
            (sorted[middle - 1] + sorted[middle]) * 0.5 : sorted[middle];

        double variance = 0.0;
        for( double value : sorted )
        {
            const double difference = value - result.Mean;
            variance += difference * difference;
        }
        result.StandardDeviation = std::sqrt( variance / (double)sorted.size( ) );

        const size_t p95Index = vaMath::Min( sorted.size( ) - 1,
            (size_t)std::ceil( 0.95 * (double)sorted.size( ) ) - 1 );
        result.P95 = sorted[p95Index];
        result.Maximum = sorted.back( );
        return result;
    }

    void CollectPreviousFrame( )
    {
        vaProfiler * profiler = vaProfiler::GetInstancePtr( );
        const vaNestedProfilerNode * node = profiler != nullptr? profiler->FindNode( "SMAA" ) : nullptr;
        if( node == nullptr )
        {
            m_passed = false;
            return;
        }

        const double gpuMilliseconds = node->GetFrameLastTotalTimeGPU( ) * 1000.0;
        const double cpuMilliseconds = node->GetFrameLastTotalTimeCPU( ) * 1000.0;
        if( std::isfinite( gpuMilliseconds ) && gpuMilliseconds > 0.0 )
            m_gpuSamples[m_currentProfile].push_back( gpuMilliseconds );
        else
            m_passed = false;
        if( std::isfinite( cpuMilliseconds ) && cpuMilliseconds > 0.0 )
            m_cpuSamples[m_currentProfile].push_back( cpuMilliseconds );
        else
            m_passed = false;

        const vaSMAAWrapper::TemporalCandidateStatistics & statistics =
            m_parent.GetSMAATemporalCandidateStatistics( );
        if( IsReadbackEnabled( m_currentProfile ) )
        {
            if( statistics.Valid )
                m_candidateCounts[m_currentProfile].push_back( (double)statistics.CandidateCount );
        }
        else if( statistics.Valid )
        {
            m_disabledReadbackUnexpectedValidCount++;
            m_passed = false;
        }
    }

    void FinishReport( AutoBenchTool & abTool )
    {
        abTool.ReportAddRowValues( { "Profile", "GPU samples", "GPU mean ms", "GPU median ms",
            "GPU stddev ms", "GPU p95 ms", "CPU samples", "CPU mean ms", "Candidate samples" } );

        for( int profile = 0; profile < c_profileCount; profile++ )
        {
            const Summary gpu = ComputeSummary( m_gpuSamples[profile] );
            const Summary cpu = ComputeSummary( m_cpuSamples[profile] );
            const Summary candidates = ComputeSummary( m_candidateCounts[profile] );
            if( gpu.Count != m_measureFrameCount || cpu.Count != m_measureFrameCount )
                m_passed = false;
            if( IsReadbackEnabled( profile ) && candidates.Count == 0 )
                m_passed = false;
            if( !IsReadbackEnabled( profile ) && candidates.Count != 0 )
                m_passed = false;

            abTool.ReportAddRowValues( {
                GetProfileID( profile ),
                vaStringTools::Format( "%d", gpu.Count ),
                vaStringTools::Format( "%.6f", gpu.Mean ),
                vaStringTools::Format( "%.6f", gpu.Median ),
                vaStringTools::Format( "%.6f", gpu.StandardDeviation ),
                vaStringTools::Format( "%.6f", gpu.P95 ),
                vaStringTools::Format( "%d", cpu.Count ),
                vaStringTools::Format( "%.6f", cpu.Mean ),
                vaStringTools::Format( "%d", candidates.Count )
            } );
        }

        abTool.ReportAddText( "\r\nReadback On minus Off characterization (single engineering smoke):\r\n" );
        abTool.ReportAddRowValues( { "Mode", "GPU delta ms", "GPU delta percent", "CPU delta ms", "CPU delta percent" } );
        for( int mode = 0; mode < 2; mode++ )
        {
            const int offProfile = mode * 2;
            const int onProfile = offProfile + 1;
            const Summary gpuOff = ComputeSummary( m_gpuSamples[offProfile] );
            const Summary gpuOn = ComputeSummary( m_gpuSamples[onProfile] );
            const Summary cpuOff = ComputeSummary( m_cpuSamples[offProfile] );
            const Summary cpuOn = ComputeSummary( m_cpuSamples[onProfile] );
            const double gpuDelta = gpuOn.Mean - gpuOff.Mean;
            const double cpuDelta = cpuOn.Mean - cpuOff.Mean;
            abTool.ReportAddRowValues( {
                mode == 0? "O-ET2X" : "O-ET2X-R",
                vaStringTools::Format( "%.6f", gpuDelta ),
                vaStringTools::Format( "%.3f", gpuOff.Mean > 0.0? 100.0 * gpuDelta / gpuOff.Mean : 0.0 ),
                vaStringTools::Format( "%.6f", cpuDelta ),
                vaStringTools::Format( "%.3f", cpuOff.Mean > 0.0? 100.0 * cpuDelta / cpuOff.Mean : 0.0 )
            } );
        }

        abTool.ReportAddText( vaStringTools::Format(
            "\r\nUnexpected valid counter samples while readback was disabled: %d\r\n",
            m_disabledReadbackUnexpectedValidCount ) );
        abTool.ReportAddText( m_passed?
            "\r\nCandidate statistics readback overhead smoke: PASS\r\n" :
            "\r\nCandidate statistics readback overhead smoke: FAIL\r\n" );
        abTool.ReportFinish( );
        m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled( true );
        VA_LOG( "SMAA candidate statistics readback overhead smoke: warmup=%d, measured=%d per profile => %s",
            m_warmupFrameCount, m_measureFrameCount, m_passed? "PASS" : "FAIL" );
    }

public:
    BenchItemSMAACandidateReadbackOverhead( CMAA2Sample & parent, float startTime,
        int warmupFrameCount, int measureFrameCount )
        : AutoBenchToolWorkItem( parent ),
        m_startTime( vaMath::Max( 0.0f, startTime ) ),
        m_warmupFrameCount( vaMath::Max( 8, warmupFrameCount ) ),
        m_measureFrameCount( vaMath::Max( 16, measureFrameCount ) )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( m_frameDeltaTime );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetVsyncForBenchmark( false );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity( );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA candidate statistics readback overhead smoke\r\n\r\n" );
            abTool.ReportAddText( "Engineering isolation test; this is not a final performance result.\r\n" );
            abTool.ReportAddText( "Only the asynchronous four-counter GPU-to-CPU diagnostic readback changes between each paired profile.\r\n" );
            abTool.ReportAddText( "Release x64, DirectX 11, SMAA Ultra, VSync Off, fixed 60 Hz camera path, no PNG capture.\r\n" );
            abTool.ReportAddText( vaStringTools::Format(
                "Start time: %.3f s, warm-up: %d frames, measurement: %d frames per profile.\r\n\r\n",
                m_startTime, m_warmupFrameCount, m_measureFrameCount ) );

            m_currentProfile = 0;
            m_currentFrame = -m_warmupFrameCount - 1;
        }

        if( m_previousFrameAvailable && m_currentFrame >= 0 )
            CollectPreviousFrame( );

        if( m_currentFrame == -1 && m_parent.HasPendingShadowmapUpdates( ) )
            return;

        if( m_previousFrameAvailable && m_currentFrame >= m_measureFrameCount - 1 )
        {
            VA_LOG( "SMAA candidate readback overhead smoke: completed %s (%d measured frames)",
                GetProfileID( m_currentProfile ), m_measureFrameCount );
            m_currentProfile++;
            if( m_currentProfile >= c_profileCount )
            {
                FinishReport( abTool );
                m_isDone = true;
                return;
            }
            m_currentFrame = -m_warmupFrameCount - 1;
            m_previousFrameAvailable = false;
        }

        m_currentFrame++;
        m_parent.SetSMAATemporalCandidateStatisticsReadbackEnabled( IsReadbackEnabled( m_currentProfile ) );
        m_parent.Settings( ).CurrentAAOption = GetProfileAAType( m_currentProfile );
        const float playTime = m_startTime + m_currentFrame * m_frameDeltaTime;
        m_parent.GetFlythroughCameraController( )->SetPlayTime( vaMath::Max( 0.0f, playTime ) );
        m_previousFrameAvailable = true;
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override { return false; }
    virtual float GetProgress( ) const override
    {
        const int framesPerProfile = m_warmupFrameCount + m_measureFrameCount;
        const int completedFrames = m_currentProfile * framesPerProfile + m_currentFrame + m_warmupFrameCount;
        return vaMath::Clamp( (float)completedFrames / (float)(framesPerProfile * c_profileCount), 0.0f, 1.0f );
    }
};

class BenchItemValidateSMAATemporalFeedback : public AutoBenchToolWorkItem
{
    static const int c_maxDiagnosticFrames = 16;
    static constexpr float c_frameDeltaTime = 1.0f / 60.0f;

    bool m_started = false;
    bool m_diagnosticsStarted = false;
    bool m_isDone = false;
    int m_currentFrame = 0;

    static string FormatHash( uint64 value )
    {
        std::ostringstream stream;
        stream << "0x" << std::hex << std::uppercase << std::setw( 16 ) << std::setfill( '0' ) << value;
        return stream.str( );
    }

    void Finish( AutoBenchTool & abTool, const vaSMAAWrapper::TemporalFeedbackDiagnostics & diagnostics )
    {
        const bool passed = diagnostics.Valid && diagnostics.Passed;
        abTool.ReportAddRowValues( { "Metric", "Value", "Acceptance", "Result" } );
        abTool.ReportAddRowValues( {
            "Completed frames",
            vaStringTools::Format( "%u", diagnostics.CompletedFrameCount ),
            ">= 3",
            diagnostics.CompletedFrameCount >= 3? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Output history checks",
            vaStringTools::Format( "%u", diagnostics.OutputHistoryCheckCount ),
            ">= 3",
            diagnostics.OutputHistoryCheckCount >= 3? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Previous history checks",
            vaStringTools::Format( "%u", diagnostics.PreviousHistoryCheckCount ),
            ">= 2",
            diagnostics.PreviousHistoryCheckCount >= 2? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Readback failures",
            vaStringTools::Format( "%u", diagnostics.ReadbackFailureCount ),
            "0",
            diagnostics.ReadbackFailureCount == 0? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Output/history mismatch bytes",
            std::to_string( diagnostics.OutputHistoryMismatchBytes ),
            "0",
            diagnostics.OutputHistoryMismatchBytes == 0? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Previous history hash mismatches",
            vaStringTools::Format( "%u", diagnostics.PreviousHistoryHashMismatchCount ),
            "0",
            diagnostics.PreviousHistoryHashMismatchCount == 0? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Last resolved history hash",
            FormatHash( diagnostics.LastResolvedHistoryHash ),
            "recorded",
            diagnostics.LastResolvedHistoryHash != 0? "PASS" : "FAIL"
        } );
        abTool.ReportAddRowValues( {
            "Last previous history hash",
            FormatHash( diagnostics.LastPreviousHistoryHash ),
            "matches the preceding resolved hash",
            diagnostics.PreviousHistoryHashMismatchCount == 0? "PASS" : "FAIL"
        } );
        abTool.ReportAddText( passed? "\r\nAggregate: PASS\r\n" : "\r\nAggregate: FAIL\r\n" );
        abTool.ReportFinish( );

        VA_LOG( "SMAA temporal feedback GPU validation: frames=%u, outputChecks=%u, previousChecks=%u, readbackFailures=%u, outputMismatchBytes=%llu, previousHashMismatches=%u => %s",
            diagnostics.CompletedFrameCount, diagnostics.OutputHistoryCheckCount, diagnostics.PreviousHistoryCheckCount,
            diagnostics.ReadbackFailureCount, (unsigned long long)diagnostics.OutputHistoryMismatchBytes,
            diagnostics.PreviousHistoryHashMismatchCount, passed? "PASS" : "FAIL" );
        m_parent.SetSMAATemporalFeedbackDiagnosticsEnabled( false );
        m_isDone = true;
    }

public:
    explicit BenchItemValidateSMAATemporalFeedback( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.Settings( ).CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X_R;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( c_frameDeltaTime );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity( );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA TSCMAA-inspired temporal history feedback GPU validation\r\n\r\n" );
            abTool.ReportAddText( "Diagnostic-only staging readback verifies exact resource bytes; it is disabled in normal and performance paths.\r\n" );
            abTool.ReportAddText( "Each frame checks output history against the displayed destination. From frame two onward, previous history is hashed and compared with the preceding resolved-history hash.\r\n" );
            abTool.ReportAddText( "Mode: O-ET2X-R, Original SMAA, edge-selective temporal, camera-motion reprojection.\r\n\r\n" );
        }

        if( !m_diagnosticsStarted )
        {
            if( m_parent.HasPendingShadowmapUpdates( ) )
                return;
            m_parent.SetSMAATemporalFeedbackDiagnosticsEnabled( true );
            m_diagnosticsStarted = true;
            m_currentFrame = 0;
            m_parent.GetFlythroughCameraController( )->SetPlayTime( 1.0f );
            return;
        }

        const vaSMAAWrapper::TemporalFeedbackDiagnostics & diagnostics =
            m_parent.GetSMAATemporalFeedbackDiagnostics( );
        if( diagnostics.Valid || diagnostics.ReadbackFailureCount > 0 || m_currentFrame >= c_maxDiagnosticFrames )
        {
            Finish( abTool, diagnostics );
            return;
        }

        m_currentFrame++;
        m_parent.GetFlythroughCameraController( )->SetPlayTime( 1.0f + m_currentFrame * c_frameDeltaTime );
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override { return false; }
    virtual float GetProgress( ) const override
    {
        return vaMath::Clamp( (float)m_currentFrame / (float)c_maxDiagnosticFrames, 0.0f, 1.0f );
    }
};

class BenchItemValidateSMAAStaticStability : public AutoBenchToolWorkItem
{
    static const int c_modeCount = 2;
    static const int c_warmupFrames = 120;
    static const int c_measureFrames = 32;
    static constexpr float c_fixedPlayTime = 1.0f;

    bool m_started = false;
    bool m_diagnosticsStarted = false;
    bool m_isDone = false;
    bool m_passed = true;
    int m_currentMode = 0;
    int m_phaseFrame = 0;
    uint32 m_sampleCount[c_modeCount] = { 0, 0 };
    uint32 m_hashMismatchCount[c_modeCount] = { 0, 0 };
    uint64 m_firstHash[c_modeCount] = { 0, 0 };
    uint64 m_lastHash[c_modeCount] = { 0, 0 };

    static const char * GetModeID( int mode )
    {
        return mode == 0? "O-ET2X" : "O-ET2X-R";
    }

    static CMAA2Sample::AAType GetModeAAType( int mode )
    {
        return mode == 0? CMAA2Sample::AAType::SMAA_O_ET2X : CMAA2Sample::AAType::SMAA_O_ET2X_R;
    }

    static string FormatHash( uint64 value )
    {
        std::ostringstream stream;
        stream << "0x" << std::hex << std::uppercase << std::setw( 16 ) << std::setfill( '0' ) << value;
        return stream.str( );
    }

    void Finish( AutoBenchTool & abTool )
    {
        abTool.ReportAddRowValues( { "Mode", "Measured hashes", "Hash changes", "First hash", "Last hash", "Result" } );
        for( int mode = 0; mode < c_modeCount; mode++ )
        {
            const bool modePassed = m_sampleCount[mode] == c_measureFrames
                && m_hashMismatchCount[mode] == 0 && m_firstHash[mode] != 0;
            m_passed &= modePassed;
            abTool.ReportAddRowValues( {
                GetModeID( mode ),
                vaStringTools::Format( "%u", m_sampleCount[mode] ),
                vaStringTools::Format( "%u", m_hashMismatchCount[mode] ),
                FormatHash( m_firstHash[mode] ),
                FormatHash( m_lastHash[mode] ),
                modePassed? "PASS" : "FAIL"
            } );
        }
        abTool.ReportAddText( m_passed? "\r\nAggregate: PASS\r\n" : "\r\nAggregate: FAIL\r\n" );
        abTool.ReportFinish( );
        VA_LOG( "SMAA static-camera temporal stability: O-ET2X changes=%u/%u, O-ET2X-R changes=%u/%u => %s",
            m_hashMismatchCount[0], m_sampleCount[0], m_hashMismatchCount[1], m_sampleCount[1],
            m_passed? "PASS" : "FAIL" );
        m_parent.SetSMAATemporalFeedbackDiagnosticsEnabled( false );
        m_isDone = true;
    }

public:
    explicit BenchItemValidateSMAAStaticStability( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;

        if( !m_started )
        {
            m_started = true;
            m_parent.Settings( ).SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / 60.0f );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.PostProcessTonemap( )->Settings( ).AutoExposureAdaptationSpeed = std::numeric_limits<float>::infinity( );
            m_parent.GetFlythroughCameraController( )->SetPlayTime( c_fixedPlayTime );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA TSCMAA-inspired static-camera temporal stability validation\r\n\r\n" );
            abTool.ReportAddText( "O-ET2X and O-ET2X-R are tested separately with fixed camera time, fixed exposure, SMAA Ultra and no PNG capture.\r\n" );
            abTool.ReportAddText( "After 120 diagnostic warm-up frames, 32 consecutive resolved-history FNV-1a hashes must remain byte-identical.\r\n" );
            abTool.ReportAddText( "This test uses diagnostic-only staging readback and does not measure performance.\r\n\r\n" );

            m_parent.Settings( ).CurrentAAOption = GetModeAAType( m_currentMode );
        }

        m_parent.GetFlythroughCameraController( )->SetPlayTime( c_fixedPlayTime );

        if( !m_diagnosticsStarted )
        {
            if( m_parent.HasPendingShadowmapUpdates( ) )
                return;
            m_parent.SetSMAATemporalFeedbackDiagnosticsEnabled( true );
            m_diagnosticsStarted = true;
            m_phaseFrame = -c_warmupFrames;
            return;
        }

        const vaSMAAWrapper::TemporalFeedbackDiagnostics & diagnostics =
            m_parent.GetSMAATemporalFeedbackDiagnostics( );
        if( diagnostics.ReadbackFailureCount > 0 )
        {
            m_passed = false;
            Finish( abTool );
            return;
        }

        if( m_phaseFrame < 0 )
        {
            m_phaseFrame++;
            return;
        }

        const uint64 resolvedHash = diagnostics.LastResolvedHistoryHash;
        if( resolvedHash == 0 )
        {
            m_passed = false;
            Finish( abTool );
            return;
        }

        if( m_sampleCount[m_currentMode] == 0 )
            m_firstHash[m_currentMode] = resolvedHash;
        else if( resolvedHash != m_lastHash[m_currentMode] )
            m_hashMismatchCount[m_currentMode]++;
        m_lastHash[m_currentMode] = resolvedHash;
        m_sampleCount[m_currentMode]++;

        if( m_sampleCount[m_currentMode] >= c_measureFrames )
        {
            m_parent.SetSMAATemporalFeedbackDiagnosticsEnabled( false );
            m_currentMode++;
            if( m_currentMode >= c_modeCount )
            {
                Finish( abTool );
                return;
            }

            m_parent.Settings( ).CurrentAAOption = GetModeAAType( m_currentMode );
            m_diagnosticsStarted = false;
            m_phaseFrame = 0;
        }
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual bool IsCapturingFrame( ) const override { return false; }
    virtual float GetProgress( ) const override
    {
        const int framesPerMode = c_warmupFrames + c_measureFrames;
        const int currentProgress = m_currentMode * framesPerMode
            + vaMath::Max( 0, m_phaseFrame + c_warmupFrames )
            + (int)m_sampleCount[vaMath::Min( m_currentMode, c_modeCount - 1 )];
        return vaMath::Clamp( (float)currentProgress / (float)(framesPerMode * c_modeCount), 0.0f, 1.0f );
    }
};

class BenchItemValidateSMAATemporalLifecycle : public AutoBenchToolWorkItem
{
    enum class Phase : int
    {
        O_T2X,
        O_T2X_R,
        O_ET2X,
        O_ET2X_R,
        A_T2X,
        A_T2X_R,
        A_ET2X,
        A_ET2X_R,
        CandidateOnlyR,
        CandidateCatmullR,
        CandidateCatmullClipR,
        CandidateCatmullClipWeight08R,
        CandidateNoJitterR,
        CandidateDeJitterR,
        CandidateDilate3x3R,
        CandidateFilteredQuarterR,
        DocumentDilate3x3R,
        DocumentFilteredQuarterR,
        ExplicitCameraCutReset,
        SceneChange,
        SceneRestore,
        Resize,
        ResizeRestore,
        Complete
    };

    Phase               m_phase                 = Phase::O_T2X;
    bool                m_started               = false;
    bool                m_isDone                = false;
    bool                m_allTransitionsPassed  = true;
    bool                m_firstTargetFrameChecked = false;
    int                 m_targetFramesObserved  = 0;
    uint32              m_phaseStartResetCount  = 0;
    uint32              m_phaseStartSeedFrameCount = 0;
    uint32              m_lastObservedFrameCount = 0;
    vaVector2i          m_originalWindowSize;
    vaVector2i          m_resizedWindowSize;

    static const char * GetPhaseName( Phase phase )
    {
        switch( phase )
        {
        case Phase::O_T2X:                  return "O-T2X mode start";
        case Phase::O_T2X_R:                return "O-T2X-R mode change";
        case Phase::O_ET2X:                 return "O-ET2X mode change";
        case Phase::O_ET2X_R:               return "O-ET2X-R mode change";
        case Phase::A_T2X:                  return "A-T2X mode change";
        case Phase::A_T2X_R:                return "A-T2X-R mode change";
        case Phase::A_ET2X:                 return "A-ET2X mode change";
        case Phase::A_ET2X_R:               return "A-ET2X-R mode change";
        case Phase::CandidateOnlyR:          return "ABL-CandidateOnly-R mode change";
        case Phase::CandidateCatmullR:       return "ABL-Candidate+Catmull-R mode change";
        case Phase::CandidateCatmullClipR:   return "ABL-Candidate+Catmull+Clip-R mode change";
        case Phase::CandidateCatmullClipWeight08R:
            return "ABL-Candidate+Catmull+Clip+W0.8-R mode change";
        case Phase::CandidateNoJitterR:
            return "ABL-CandidateOnly-NoJitter-R mode change";
        case Phase::CandidateDeJitterR:
            return "ABL-Candidate-DeJitter-R mode change";
        case Phase::CandidateDilate3x3R:
            return "ABL-Candidate-Jitter-Dilate3x3-R mode change";
        case Phase::CandidateFilteredQuarterR:
            return "ABL-Candidate-Jitter-FilteredQuarter-R mode change";
        case Phase::DocumentDilate3x3R:
            return "ABL-Document-Dilate3x3-R mode change";
        case Phase::DocumentFilteredQuarterR:
            return "ABL-Document-FilteredQuarter-R mode change";
        case Phase::ExplicitCameraCutReset: return "explicit camera-cut reset";
        case Phase::SceneChange:            return "scene change";
        case Phase::SceneRestore:           return "scene restore";
        case Phase::Resize:                 return "resolution change";
        case Phase::ResizeRestore:          return "resolution restore";
        case Phase::Complete:               return "complete";
        default:                            return "unknown";
        }
    }

    bool TargetSizeMatches( const vaSMAAWrapper::TemporalLifecycleDiagnostics & diagnostics ) const
    {
        if( m_phase == Phase::Resize )
            return diagnostics.LastWidth == (uint32)m_resizedWindowSize.x && diagnostics.LastHeight == (uint32)m_resizedWindowSize.y;
        if( m_phase == Phase::ResizeRestore )
            return diagnostics.LastWidth == (uint32)m_originalWindowSize.x && diagnostics.LastHeight == (uint32)m_originalWindowSize.y;
        return true;
    }

    int RequiredTargetFrames( ) const
    {
        return (int)m_phase <= (int)Phase::DocumentFilteredQuarterR? 3 : 2;
    }

    void EnterPhase( Phase phase )
    {
        m_phase = phase;
        const vaSMAAWrapper::TemporalLifecycleDiagnostics & diagnostics = m_parent.GetSMAATemporalLifecycleDiagnostics( );
        m_phaseStartResetCount = diagnostics.ResetCount;
        m_phaseStartSeedFrameCount = diagnostics.SeedFrameCount;
        m_lastObservedFrameCount = diagnostics.CompletedFrameCount;
        m_targetFramesObserved = 0;
        m_firstTargetFrameChecked = false;

        switch( phase )
        {
        case Phase::O_T2X:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_T2X;
            // The initial mode may already be selected in persisted settings,
            // so explicitly establish a known reset boundary for phase zero.
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
            break;
        case Phase::O_T2X_R:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_T2X_R;
            break;
        case Phase::O_ET2X:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X;
            break;
        case Phase::O_ET2X_R:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X_R;
            break;
        case Phase::A_T2X:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_A_T2X;
            break;
        case Phase::A_T2X_R:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_A_T2X_R;
            break;
        case Phase::A_ET2X:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_A_ET2X;
            break;
        case Phase::A_ET2X_R:
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_A_ET2X_R;
            break;
        case Phase::CandidateOnlyR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R;
            break;
        case Phase::CandidateCatmullR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_R;
            break;
        case Phase::CandidateCatmullClipR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_R;
            break;
        case Phase::CandidateCatmullClipWeight08R:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_CATMULL_CLIP_WEIGHT08_R;
            break;
        case Phase::CandidateNoJitterR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_NO_JITTER;
            break;
        case Phase::CandidateDeJitterR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DEJITTER_BASE;
            break;
        case Phase::CandidateDilate3x3R:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_DILATE3X3;
            break;
        case Phase::CandidateFilteredQuarterR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_CANDIDATE_ONLY_R_FILTERED_QUARTER;
            break;
        case Phase::DocumentDilate3x3R:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_DILATE3X3;
            break;
        case Phase::DocumentFilteredQuarterR:
            m_parent.Settings().CurrentAAOption =
                CMAA2Sample::AAType::SMAA_O_ABLATION_DOCUMENT_R_FILTERED_QUARTER;
            break;
        case Phase::ExplicitCameraCutReset:
            // LoadCamera and other known camera cuts use this same history-reset
            // entry point; no arbitrary motion threshold is introduced.
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
            break;
        case Phase::SceneChange:
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::MinecraftLostEmpire;
            break;
        case Phase::SceneRestore:
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            break;
        case Phase::Resize:
            m_parent.SetWindowClientAreaSizeForDiagnostics( m_resizedWindowSize );
            break;
        case Phase::ResizeRestore:
            m_parent.SetWindowClientAreaSizeForDiagnostics( m_originalWindowSize );
            break;
        case Phase::Complete:
            break;
        }
    }

public:
    explicit BenchItemValidateSMAATemporalLifecycle( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;
        if( !m_started )
        {
            m_started = true;
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / 60.0f );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_originalWindowSize = m_parent.GetApplication().GetWindowClientAreaSize( );
            m_resizedWindowSize = vaVector2i( vaMath::Max( 320, m_originalWindowSize.x - 64 ),
                vaMath::Max( 240, m_originalWindowSize.y - 64 ) );
            m_parent.SetSMAATemporalLifecycleDiagnosticsEnabled( true );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA eight-case plus controlled component, current-edge expansion, and hybrid resolve ablation temporal lifecycle engineering validation\r\n\r\n" );
            abTool.ReportAddText( "Validates seed/resolve state, ping-pong indices, jitter/subsample pairing,\r\n" );
            abTool.ReportAddText( "first-frame reprojection matrices, mode/scene/camera-cut reset, and resize recreation.\r\n" );
            abTool.ReportAddText( "This is not a formal quality or performance measurement.\r\n\r\n" );
            abTool.ReportAddRowValues( { "Phase", "Reset observed", "First frame seeded", "Result" } );
            EnterPhase( Phase::O_T2X );
            return;
        }

        const vaSMAAWrapper::TemporalLifecycleDiagnostics & diagnostics = m_parent.GetSMAATemporalLifecycleDiagnostics( );
        if( m_phase == Phase::Complete )
        {
            const bool aggregatePassed = diagnostics.Passed && m_allTransitionsPassed
                && diagnostics.SeedFrameCount >= 23
                && diagnostics.ResolvedFrameCount > diagnostics.SeedFrameCount
                && diagnostics.ReprojectionFrameCount > 0;
            VA_LOG( "SMAA temporal lifecycle validation: resets=%u, frames=%u, seed=%u, resolve=%u, reprojection=%u, failures=%u => %s",
                diagnostics.ResetCount, diagnostics.CompletedFrameCount, diagnostics.SeedFrameCount,
                diagnostics.ResolvedFrameCount, diagnostics.ReprojectionFrameCount,
                diagnostics.GetFailureCount( ), aggregatePassed? "PASS" : "FAIL" );
            abTool.ReportAddText( vaStringTools::Format(
                "\r\nAggregate: resets %u, frames %u, seed %u, resolve %u, reprojection %u, failures %u => %s\r\n",
                diagnostics.ResetCount, diagnostics.CompletedFrameCount, diagnostics.SeedFrameCount,
                diagnostics.ResolvedFrameCount, diagnostics.ReprojectionFrameCount,
                diagnostics.GetFailureCount( ), aggregatePassed? "PASS" : "FAIL" ) );
            m_allTransitionsPassed = m_allTransitionsPassed && aggregatePassed;
            m_parent.SetSMAATemporalLifecycleDiagnosticsEnabled( false );
            abTool.ReportFinish( );
            m_isDone = true;
            return;
        }

        if( diagnostics.CompletedFrameCount == m_lastObservedFrameCount )
            return;
        m_lastObservedFrameCount = diagnostics.CompletedFrameCount;

        if( !TargetSizeMatches( diagnostics ) )
            return;

        m_targetFramesObserved++;
        if( !m_firstTargetFrameChecked )
        {
            const bool resetObserved = diagnostics.ResetCount > m_phaseStartResetCount;
            // Shader compilation or scene setup can pause AutoBench ticks while
            // rendering continues. Use the cumulative seed counter rather than
            // assuming the latest completed frame is still the seed frame.
            const bool seeded = diagnostics.SeedFrameCount > m_phaseStartSeedFrameCount;
            const bool phasePassed = resetObserved && seeded && diagnostics.Passed;
            m_allTransitionsPassed = m_allTransitionsPassed && phasePassed;
            m_firstTargetFrameChecked = true;
            abTool.ReportAddRowValues( { GetPhaseName( m_phase ), resetObserved? "yes" : "no",
                seeded? "yes" : "no", phasePassed? "PASS" : "FAIL" } );
            VA_LOG( "SMAA temporal lifecycle phase [%s]: reset=%s, seeded=%s => %s",
                GetPhaseName( m_phase ), resetObserved? "yes" : "no", seeded? "yes" : "no",
                phasePassed? "PASS" : "FAIL" );
        }

        if( m_targetFramesObserved < RequiredTargetFrames( ) )
            return;

        EnterPhase( (Phase)((int)m_phase + 1) );
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual float GetProgress( ) const override { return (float)(int)m_phase / (float)(int)Phase::Complete; }
};

class BenchItemValidateSMAATemporalVelocity : public AutoBenchToolWorkItem
{
    enum class Phase : int
    {
        StaticCamera,
        CameraRightTranslation,
        Complete
    };

    Phase               m_phase                 = Phase::StaticCamera;
    bool                m_started               = false;
    bool                m_isDone                = false;
    bool                m_staticPassed          = false;
    bool                m_translationPassed     = false;

public:
    explicit BenchItemValidateSMAATemporalVelocity( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;
        if( !m_started )
        {
            m_started = true;
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X_R;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / 60.0f );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.SetSMAATemporalVelocityDiagnosticMode(
                vaSMAAWrapper::TemporalVelocityDiagnosticMode::StaticCameraZero );
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA camera-motion GPU velocity engineering validation\r\n\r\n" );
            abTool.ReportAddText( "O-ET2X-R only; object motion vectors are not connected.\r\n" );
            abTool.ReportAddText( "The diagnostic staging readback is enabled only for this test and is not a performance path.\r\n\r\n" );
            abTool.ReportAddRowValues( { "Phase", "Mean X", "Mean Y", "Max abs", "Negative-X ratio", "History UV in bounds", "Result" } );
            return;
        }

        const vaSMAAWrapper::TemporalVelocityDiagnostics & diagnostics =
            m_parent.GetSMAATemporalVelocityDiagnostics( );
        if( !diagnostics.Valid )
            return;

        if( m_phase == Phase::StaticCamera )
        {
            m_staticPassed = diagnostics.Mode == vaSMAAWrapper::TemporalVelocityDiagnosticMode::StaticCameraZero
                && diagnostics.Passed;
            abTool.ReportAddRowValues( {
                "Static camera",
                vaStringTools::Format( "%.8f", diagnostics.MeanVelocity.x ),
                vaStringTools::Format( "%.8f", diagnostics.MeanVelocity.y ),
                vaStringTools::Format( "%.8f", diagnostics.MaximumAbsoluteVelocity ),
                "-",
                vaStringTools::Format( "%.3f%%", 100.0f * diagnostics.GetHistoryUVInBoundsRatio( ) ),
                m_staticPassed? "PASS" : "FAIL" } );

            const vaVector3 cameraRight = m_parent.Camera()->GetWorldMatrix( ).GetAxisX( ).Normalized( );
            m_parent.Camera()->SetPosition( m_parent.Camera()->GetPosition( ) + cameraRight * 0.01f );
            m_parent.SetSMAATemporalVelocityDiagnosticMode(
                vaSMAAWrapper::TemporalVelocityDiagnosticMode::CameraRightTranslation );
            m_phase = Phase::CameraRightTranslation;
            return;
        }

        if( m_phase == Phase::CameraRightTranslation )
        {
            m_translationPassed = diagnostics.Mode == vaSMAAWrapper::TemporalVelocityDiagnosticMode::CameraRightTranslation
                && diagnostics.Passed;
            abTool.ReportAddRowValues( {
                "Camera translated +right by 0.01 m",
                vaStringTools::Format( "%.8f", diagnostics.MeanVelocity.x ),
                vaStringTools::Format( "%.8f", diagnostics.MeanVelocity.y ),
                vaStringTools::Format( "%.8f", diagnostics.MaximumAbsoluteVelocity ),
                vaStringTools::Format( "%.3f%%", 100.0f * diagnostics.GetExpectedNegativeXRatio( ) ),
                vaStringTools::Format( "%.3f%%", 100.0f * diagnostics.GetHistoryUVInBoundsRatio( ) ),
                m_translationPassed? "PASS" : "FAIL" } );

            const bool aggregatePassed = m_staticPassed && m_translationPassed;
            VA_LOG( "SMAA GPU velocity validation: static=%s, camera-right=%s => %s",
                m_staticPassed? "PASS" : "FAIL", m_translationPassed? "PASS" : "FAIL",
                aggregatePassed? "PASS" : "FAIL" );
            abTool.ReportAddText( vaStringTools::Format( "\r\nAggregate: static %s, camera-right %s => %s\r\n",
                m_staticPassed? "PASS" : "FAIL", m_translationPassed? "PASS" : "FAIL",
                aggregatePassed? "PASS" : "FAIL" ) );
            m_parent.SetSMAATemporalVelocityDiagnosticMode(
                vaSMAAWrapper::TemporalVelocityDiagnosticMode::Disabled );
            abTool.ReportFinish( );
            m_phase = Phase::Complete;
            m_isDone = true;
        }
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual float GetProgress( ) const override { return (float)(int)m_phase / (float)(int)Phase::Complete; }
};

class BenchItemValidateSMAACatmullRom : public AutoBenchToolWorkItem
{
    bool                m_started               = false;
    bool                m_isDone                = false;

public:
    explicit BenchItemValidateSMAACatmullRom( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;
        if( !m_started )
        {
            m_started = true;
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / 60.0f );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.RequestSMAACatmullRomDiagnostics( );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA TSCMAA-inspired Catmull-Rom 5-tap engineering validation\r\n\r\n" );
            abTool.ReportAddText( "The exact 5-tap coordinates and weights are an explicit adaptation because the public Intel TSCMAA document does not publish them.\r\n" );
            abTool.ReportAddText( "GPU validation uses an 8x8 RGBA32F source and a 16x16 UV grid spanning [-0.1, 1.1] to exercise clamp sampling.\r\n" );
            abTool.ReportAddText( "CPU characterization compares the 5-tap approximation with a separable 16-tap Catmull-Rom reference on 4,096 UVs.\r\n\r\n" );
            abTool.ReportAddRowValues( { "Metric", "Samples", "Value", "Acceptance / meaning", "Result" } );
            return;
        }

        const vaSMAAWrapper::CatmullRomDiagnostics & diagnostics =
            m_parent.GetSMAACatmullRomDiagnostics( );
        if( !diagnostics.Valid )
            return;

        abTool.ReportAddRowValues( {
            "Cubic/effective 5-tap weight sum maximum error", "4,097 fractions + 257x257 pairs",
            vaStringTools::Format( "%.9f", diagnostics.MaximumWeightSumError ),
            "<= 0.000002", diagnostics.MaximumWeightSumError <= 2.0e-6f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "Cubic mirror symmetry maximum error", "4,097 fractions",
            vaStringTools::Format( "%.9f", diagnostics.MaximumSymmetryError ),
            "<= 0.000002", diagnostics.MaximumSymmetryError <= 2.0e-6f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "GPU constant-channel maximum error",
            vaStringTools::Format( "%u GPU samples", diagnostics.GPUComparisonSampleCount ),
            vaStringTools::Format( "%.9f", diagnostics.GPUConstantMaximumError ),
            "<= 0.000020", diagnostics.GPUConstantMaximumError <= 2.0e-5f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "GPU shader vs CPU 5-tap maximum error",
            vaStringTools::Format( "%u GPU samples", diagnostics.GPUComparisonSampleCount ),
            vaStringTools::Format( "%.9f", diagnostics.GPUToCPU5TapMaximumError ),
            "<= 0.005000 (hardware linear-filter precision)", diagnostics.GPUToCPU5TapMaximumError <= 5.0e-3f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "GPU shader vs CPU 5-tap RMSE",
            vaStringTools::Format( "%u GPU samples", diagnostics.GPUComparisonSampleCount ),
            vaStringTools::Format( "%.9f", diagnostics.GPUToCPU5TapRMSE ),
            "recorded characterization", "-" } );
        abTool.ReportAddRowValues( {
            "CPU 5-tap vs CPU 16-tap maximum error",
            vaStringTools::Format( "%u CPU samples", diagnostics.CPUReferenceSampleCount ),
            vaStringTools::Format( "%.9f", diagnostics.CPU5TapTo16TapMaximumError ),
            "recorded approximation error", "-" } );
        abTool.ReportAddRowValues( {
            "CPU 5-tap vs CPU 16-tap RMSE",
            vaStringTools::Format( "%u CPU samples", diagnostics.CPUReferenceSampleCount ),
            vaStringTools::Format( "%.9f", diagnostics.CPU5TapTo16TapRMSE ),
            "recorded approximation error", "-" } );
        abTool.ReportAddText( diagnostics.Passed? "\r\nAggregate: PASS\r\n" : "\r\nAggregate: FAIL\r\n" );
        abTool.ReportFinish( );
        m_isDone = true;
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual float GetProgress( ) const override { return m_isDone? 1.0f : 0.5f; }
};

class BenchItemValidateSMAAVarianceClipping : public AutoBenchToolWorkItem
{
    bool                m_started               = false;
    bool                m_isDone                = false;

public:
    explicit BenchItemValidateSMAAVarianceClipping( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;
        if( !m_started )
        {
            m_started = true;
            m_parent.Settings().SceneChoice = CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / 60.0f );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.RequestSMAAVarianceClippingDiagnostics( );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA TSCMAA-inspired YCoCg variance-clipping engineering validation\r\n\r\n" );
            abTool.ReportAddText( "The public Intel document specifies YCoCg variance clipping; the 3x3 statistics, gamma=1.0, segment clipping formula and tolerances are explicit adaptation choices.\r\n" );
            abTool.ReportAddText( "The actual GPU shader is compared with a CPU mirror for constant-neighbourhood, valid-history and outlier-history cases.\r\n\r\n" );
            abTool.ReportAddRowValues( { "Metric", "Value", "Acceptance", "Result" } );
            return;
        }

        const vaSMAAWrapper::VarianceClippingDiagnostics & diagnostics =
            m_parent.GetSMAAVarianceClippingDiagnostics( );
        if( !diagnostics.Valid )
            return;

        abTool.ReportAddRowValues( {
            "Finite GPU pixels",
            vaStringTools::Format( "%u / %u", diagnostics.FinitePixelCount, diagnostics.PixelCount ),
            "all", diagnostics.FinitePixelCount == diagnostics.PixelCount? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "RGB-YCoCg-RGB round-trip maximum error",
            vaStringTools::Format( "%.9f", diagnostics.RGBYCoCgRoundTripMaximumError ),
            "<= 0.000002", diagnostics.RGBYCoCgRoundTripMaximumError <= 2.0e-6f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "Constant-neighbourhood maximum error",
            vaStringTools::Format( "%.9f", diagnostics.ConstantCaseMaximumError ),
            "<= 0.000020", diagnostics.ConstantCaseMaximumError <= 2.0e-5f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "Inside-history maximum error",
            vaStringTools::Format( "%.9f", diagnostics.InsideHistoryMaximumError ),
            "<= 0.000020", diagnostics.InsideHistoryMaximumError <= 2.0e-5f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "GPU shader vs CPU reference maximum error",
            vaStringTools::Format( "%.9f", diagnostics.GPUToCPUReferenceMaximumError ),
            "<= 0.000050", diagnostics.GPUToCPUReferenceMaximumError <= 5.0e-5f? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "GPU shader vs CPU reference RMSE",
            vaStringTools::Format( "%.9f", diagnostics.GPUToCPUReferenceRMSE ),
            "recorded characterization", "-" } );
        abTool.ReportAddRowValues( {
            "Outlier histories rejected",
            vaStringTools::Format( "%u / 64", diagnostics.OutlierRejectedCount ),
            "64 / 64", diagnostics.OutlierRejectedCount == 64? "PASS" : "FAIL" } );
        abTool.ReportAddRowValues( {
            "Clipped outlier box violations",
            vaStringTools::Format( "%u", diagnostics.OutlierBoxViolationCount ),
            "0", diagnostics.OutlierBoxViolationCount == 0? "PASS" : "FAIL" } );
        abTool.ReportAddText( diagnostics.Passed? "\r\nAggregate: PASS\r\n" : "\r\nAggregate: FAIL\r\n" );
        abTool.ReportFinish( );
        m_isDone = true;
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual float GetProgress( ) const override { return m_isDone? 1.0f : 0.5f; }
};

class BenchItemValidateSMAACandidatePolicy : public AutoBenchToolWorkItem
{
    const CMAA2Sample::SceneSelectionType m_scenes[2] =
    {
        CMAA2Sample::SceneSelectionType::LumberyardBistro,
        CMAA2Sample::SceneSelectionType::MinecraftLostEmpire
    };
    const char *        m_sceneNames[2]          = { "LumberyardBistro", "MinecraftLostEmpire" };
    const float         m_removalAmounts[5]      = { 0.0f, 0.25f, 0.5f, 0.75f, 1.0f };
    int                 m_sceneIndex             = 0;
    int                 m_removalIndex           = 0;
    uint32              m_expectedBaseCount      = 0;
    uint32              m_previousCandidateCount = 0;
    bool                m_started                = false;
    bool                m_lightingStableArmed    = false;
    bool                m_passed                 = true;
    bool                m_isDone                 = false;

public:
    explicit BenchItemValidateSMAACandidatePolicy( CMAA2Sample & parent )
        : AutoBenchToolWorkItem( parent )
    {
    }

protected:
    virtual void Tick( AutoBenchTool & abTool, float deltaTime ) override
    {
        deltaTime;
        if( !m_started )
        {
            m_started = true;
            m_parent.Settings().SceneChoice = m_scenes[m_sceneIndex];
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SMAA_O_ET2X_R;
            m_parent.SetRequireDeterminism( true );
            m_parent.SetFixedDeltaTime( 1.0f / 60.0f );
            m_parent.SetSMAAPreset( vaSMAAWrapper::Preset::PRESET_ULTRA );
            m_parent.SetFlythroughCameraEnabled( false );
            m_parent.SetSMAACandidatePolicyOverride(
                true, vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant );
            m_parent.SetSMAANonDominantRemovalOverride( true, m_removalAmounts[m_removalIndex] );

            abTool.ReportStart( );
            abTool.ReportAddText( "SMAA TSCMAA-inspired Intel-family candidate policy validation\r\n\r\n" );
            abTool.ReportAddText( "The local connected-edge formula is a documented adaptation of Intel CMAA2 structure plus the public TSCMAA threshold/removal defaults, not recovered official TSCMAA source.\r\n" );
            abTool.ReportAddText( "Each scene is held at a fixed camera; statistics are accepted only after shadow-map updates finish.\r\n\r\n" );
            abTool.ReportAddRowValues( { "Scene", "Removal", "Base edges", "Candidates", "Candidate/base", "Indirect process", "Checks", "Result" } );
            return;
        }

        if( !m_lightingStableArmed )
        {
            if( m_parent.HasPendingShadowmapUpdates( ) )
                return;
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
            m_lightingStableArmed = true;
            return;
        }

        const vaSMAAWrapper::TemporalCandidateStatistics & statistics =
            m_parent.GetSMAATemporalCandidateStatistics( );
        if( !statistics.Valid || statistics.Policy != vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant )
            return;

        bool stepPassed = statistics.ProcessCount == statistics.CandidateCount;
        string checks = "process=candidate";
        if( m_removalIndex == 0 )
        {
            m_expectedBaseCount = statistics.BaseEdgeCount;
            m_previousCandidateCount = statistics.CandidateCount;
            stepPassed = stepPassed && statistics.CandidateCount == statistics.BaseEdgeCount;
            checks += ", removal0=base";
        }
        else
        {
            stepPassed = stepPassed && statistics.BaseEdgeCount == m_expectedBaseCount;
            stepPassed = stepPassed && statistics.CandidateCount <= m_previousCandidateCount;
            checks += ", base stable, monotonic";
            m_previousCandidateCount = statistics.CandidateCount;
        }
        m_passed = m_passed && stepPassed;

        abTool.ReportAddRowValues( {
            m_sceneNames[m_sceneIndex],
            vaStringTools::Format( "%.2f", m_removalAmounts[m_removalIndex] ),
            vaStringTools::Format( "%u", statistics.BaseEdgeCount ),
            vaStringTools::Format( "%u", statistics.CandidateCount ),
            vaStringTools::Format( "%.3f%%", 100.0f * statistics.GetCandidateToBaseRatio( ) ),
            vaStringTools::Format( "%u", statistics.ProcessCount ),
            checks,
            stepPassed? "PASS" : "FAIL" } );

        m_removalIndex++;
        if( m_removalIndex < 5 )
        {
            m_parent.SetSMAANonDominantRemovalOverride( true, m_removalAmounts[m_removalIndex] );
            return;
        }

        m_sceneIndex++;
        if( m_sceneIndex < 2 )
        {
            m_removalIndex = 0;
            m_expectedBaseCount = 0;
            m_previousCandidateCount = 0;
            m_lightingStableArmed = false;
            m_parent.Settings().SceneChoice = m_scenes[m_sceneIndex];
            m_parent.SetSMAANonDominantRemovalOverride( true, m_removalAmounts[m_removalIndex] );
            m_parent.ResetSMAATemporalHistoryForDiagnostics( );
            return;
        }

        abTool.ReportAddText( m_passed? "\r\nAggregate: PASS\r\n" : "\r\nAggregate: FAIL\r\n" );
        m_parent.SetSMAANonDominantRemovalOverride( false, 0.5f );
        m_parent.SetSMAACandidatePolicyOverride(
            false, vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant );
        abTool.ReportFinish( );
        m_isDone = true;
    }

    virtual void OnRender( AutoBenchTool & ) override {}
    virtual bool IsDone( AutoBenchTool & ) const override { return m_isDone; }
    virtual float GetProgress( ) const override
    {
        return m_isDone? 1.0f : (float)(m_sceneIndex * 5 + m_removalIndex) / 10.0f;
    }
};

void CMAA2Sample::ProcessCommandLineCaptureRequest()
{
    if (m_commandLineCaptureProcessed)
        return;
    m_commandLineCaptureProcessed = true;

    // User settings are loaded after external assets. Restore the explicit
    // command-line scene selection here so a free-running preview cannot be
    // switched back to the previously saved scene before the first frame.
    if (HasPowerPlantPreview())
    {
        for (const auto& parameter : m_application.GetCommandLineParameters())
        {
            if (_wcsicmp(parameter.first.c_str(), L"smaaPowerPlantPreviewCache") == 0)
            {
                m_settings.SceneChoice = SceneSelectionType::PowerPlantThinGeometry;
                m_flythroughPlay = false;
                break;
            }
        }
    }
    if (HasSanMiguelScene())
    {
        for (const auto& parameter : m_application.GetCommandLineParameters())
        {
            if (_wcsicmp(parameter.first.c_str(), L"smaaSanMiguelCache") == 0)
            {
                m_settings.SceneChoice = SceneSelectionType::SanMiguelTextured;
                m_flythroughPlay = false;
                break;
            }
        }
    }

    for (const auto& parameter : m_application.GetCommandLineParameters())
    {
        if (_wcsicmp(parameter.first.c_str(), L"smaaCandidatePolicyOverride") == 0)
        {
            int policy = -1;
            std::wistringstream values(parameter.second);
            if (!(values >> policy) || policy < -1 || policy > 2)
            {
                VA_LOG_ERROR("Invalid -smaaCandidatePolicyOverride value; expected -1 (disabled), 0 (all base), 1 (Intel-family), or 2 (experimental)");
                return;
            }
            m_SMAA->SetCandidatePolicyOverride(policy >= 0,
                policy >= 0? (vaSMAAWrapper::CandidatePolicy)policy : vaSMAAWrapper::CandidatePolicy::IntelFamilyNonDominant);
            VA_LOG("SMAA candidate policy diagnostic override: %s",
                policy >= 0? GetCandidatePolicyName((vaSMAAWrapper::CandidatePolicy)policy) : "disabled");
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaCandidateExpansionOverride") == 0)
        {
            int expansion = -1;
            std::wistringstream values(parameter.second);
            if (!(values >> expansion) || expansion < -1 || expansion > 2)
            {
                VA_LOG_ERROR("Invalid -smaaCandidateExpansionOverride value; expected -1 (disabled), 0 (none), 1 (current-edge 3x3 dilation), or 2 (filtered quarter)");
                return;
            }
            m_SMAA->SetCandidateExpansionOverride(expansion >= 0,
                expansion >= 0? (vaSMAAWrapper::CandidateExpansion)expansion : vaSMAAWrapper::CandidateExpansion::None);
            VA_LOG("SMAA candidate expansion diagnostic override: %s",
                expansion >= 0? GetCandidateExpansionName((vaSMAAWrapper::CandidateExpansion)expansion) : "disabled");
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaHistorySamplerOverride") == 0)
        {
            int sampler = -1;
            std::wistringstream values(parameter.second);
            if (!(values >> sampler) || sampler < -1 || sampler > 1)
            {
                VA_LOG_ERROR("Invalid -smaaHistorySamplerOverride value; expected -1 (disabled), 0 (bilinear), or 1 (Catmull-Rom 5-tap)");
                return;
            }
            m_SMAA->SetHistorySamplerOverride(sampler >= 0,
                sampler >= 0? (vaSMAAWrapper::HistorySampler)sampler : vaSMAAWrapper::HistorySampler::Bilinear);
            VA_LOG("SMAA history sampler diagnostic override: %s",
                sampler >= 0? GetHistorySamplerName((vaSMAAWrapper::HistorySampler)sampler) : "disabled");
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaHistoryClippingOverride") == 0)
        {
            int clipping = -1;
            std::wistringstream values(parameter.second);
            if (!(values >> clipping) || clipping < -1 || clipping > 1)
            {
                VA_LOG_ERROR("Invalid -smaaHistoryClippingOverride value; expected -1 (disabled), 0 (off), or 1 (YCoCg variance)");
                return;
            }
            m_SMAA->SetHistoryClippingOverride(clipping >= 0,
                clipping >= 0? (vaSMAAWrapper::HistoryClipping)clipping : vaSMAAWrapper::HistoryClipping::Off);
            VA_LOG("SMAA history clipping diagnostic override: %s",
                clipping >= 0? GetHistoryClippingName((vaSMAAWrapper::HistoryClipping)clipping) : "disabled");
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaTemporalDebugView") == 0)
        {
            int debugView = 0;
            std::wistringstream values(parameter.second);
            if (!(values >> debugView) || debugView < 0 || debugView > 6)
            {
                VA_LOG_ERROR("Invalid -smaaTemporalDebugView value; expected 0 (off), 1 (base edges), 2 (selected candidates), 3 (current spatial), 4 (history before clipping), 5 (history after clipping), or 6 (clipping delta)");
                return;
            }
            m_SMAA->SetTemporalDebugView((vaSMAAWrapper::TemporalDebugView)debugView);
            VA_LOG("SMAA temporal debug view: %d", debugView);
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaCandidateForcedCount") == 0)
        {
            unsigned long long forcedCount = 0;
            std::wistringstream values(parameter.second);
            if (!(values >> forcedCount) || forcedCount > std::numeric_limits<uint32>::max())
            {
                VA_LOG_ERROR("Invalid -smaaCandidateForcedCount value; expected an unsigned 32-bit candidate count");
                return;
            }
            m_SMAA->SetForcedCandidateCountForDiagnostics(true, (uint32)forcedCount);
            VA_LOG("SMAA forced candidate-count diagnostics: requested=%u", (uint32)forcedCount);
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaCandidateStatisticsReadback") == 0)
        {
            int enabled = 1;
            std::wistringstream values(parameter.second);
            if (!(values >> enabled) || enabled < 0 || enabled > 1)
            {
                VA_LOG_ERROR("Invalid -smaaCandidateStatisticsReadback value; expected 0 or 1");
                return;
            }
            m_SMAA->SetTemporalCandidateStatisticsReadbackEnabled(enabled != 0);
            VA_LOG("SMAA candidate statistics GPU readback: %s", enabled != 0? "enabled" : "disabled");
        }
        else if (_wcsicmp(parameter.first.c_str(), L"smaaTemporalLifecycleDiagnostics") == 0)
        {
            int enabled = 1;
            if (!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if (!(values >> enabled) || enabled < 0 || enabled > 1)
                {
                    VA_LOG_ERROR("Invalid -smaaTemporalLifecycleDiagnostics value; expected 0 or 1");
                    return;
                }
            }
            m_SMAA->SetTemporalLifecycleDiagnosticsEnabled(enabled != 0);
            VA_LOG("SMAA temporal lifecycle diagnostics: %s", enabled != 0? "enabled" : "disabled");
        }
    }

    for (const auto& parameter : m_application.GetCommandLineParameters())
    {
        if(_wcsicmp(parameter.first.c_str(), L"smaaPowerPlantPreviewCapture") == 0)
        {
            int warmupFrameCount = 60;
            if(!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if(!(values >> warmupFrameCount) || warmupFrameCount < 0 || warmupFrameCount > 600)
                {
                    VA_LOG_ERROR("Invalid -smaaPowerPlantPreviewCapture value; expected [warmupFrames] between 0 and 600");
                    return;
                }
            }
            if(!HasPowerPlantPreview())
            {
                VA_LOG_ERROR("-smaaPowerPlantPreviewCapture requires -smaaPowerPlantPreviewCache <absolute .smaapp path>");
                return;
            }
            m_autoBench->AddTask(std::make_shared<BenchItemCaptureSMAAExternalScenePreview>(
                *this, SceneSelectionType::PowerPlantThinGeometry, warmupFrameCount,
                L"powerplant_preview.png",
                "UNC Power Plant external real-geometry preview capture"));
            m_externalScenePreviewDeadline = m_application.GetTimeFromStart() + 180.0;
            m_externalScenePreviewNextStatusLog = m_application.GetTimeFromStart();
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued UNC Power Plant engineering preview capture: warm-up=%d", warmupFrameCount);
            return;
        }

        if(_wcsicmp(parameter.first.c_str(), L"smaaSanMiguelPreviewCapture") == 0)
        {
            int warmupFrameCount = 60;
            if(!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if(!(values >> warmupFrameCount) || warmupFrameCount < 0 || warmupFrameCount > 600)
                {
                    VA_LOG_ERROR("Invalid -smaaSanMiguelPreviewCapture value; expected [warmupFrames] between 0 and 600");
                    return;
                }
            }
            if(!HasSanMiguelScene())
            {
                VA_LOG_ERROR("-smaaSanMiguelPreviewCapture requires -smaaSanMiguelCache <absolute .smaasm path>");
                return;
            }
            m_autoBench->AddTask(std::make_shared<BenchItemCaptureSMAAExternalScenePreview>(
                *this, SceneSelectionType::SanMiguelTextured, warmupFrameCount,
                L"san_miguel_preview.png",
                "San Miguel 2.1 external textured-scene preview capture"));
            m_externalScenePreviewDeadline = m_application.GetTimeFromStart() + 180.0;
            m_externalScenePreviewNextStatusLog = m_application.GetTimeFromStart();
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued San Miguel engineering preview capture: warm-up=%d", warmupFrameCount);
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaStaticStabilityTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAAStaticStability>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA O-ET2X/O-ET2X-R static-camera temporal stability validation");
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaTemporalFeedbackTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAATemporalFeedback>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA temporal output/history feedback GPU validation");
            return;
        }

        const bool originalPerformanceSmoke = _wcsicmp(parameter.first.c_str(), L"smaaOriginalFourPerformanceSmoke") == 0;
        const bool originalPerformanceBenchmark = _wcsicmp(parameter.first.c_str(), L"smaaOriginalFourPerformanceBenchmark") == 0;
        const bool eightCasePerformanceSmoke = _wcsicmp(parameter.first.c_str(), L"smaaEightCasePerformanceSmoke") == 0;
        const bool eightCasePerformanceBenchmark = _wcsicmp(parameter.first.c_str(), L"smaaEightCasePerformanceBenchmark") == 0;
        const bool candidateAblationPerformanceSmoke =
            _wcsicmp(parameter.first.c_str(), L"smaaCandidateOnlyAblationPerformanceSmoke") == 0;
        const bool candidateAblationPerformanceBenchmark =
            _wcsicmp(parameter.first.c_str(), L"smaaCandidateOnlyAblationPerformanceBenchmark") == 0;
        const bool componentAblationPerformanceSmoke =
            _wcsicmp(parameter.first.c_str(), L"smaaTemporalComponentAblationPerformanceSmoke") == 0;
        const bool componentAblationPerformanceBenchmark =
            _wcsicmp(parameter.first.c_str(), L"smaaTemporalComponentAblationPerformanceBenchmark") == 0;
        const bool currentEdgeDilationPerformanceSmoke =
            _wcsicmp(parameter.first.c_str(), L"smaaCurrentEdgeDilationPerformanceSmoke") == 0;
        const bool currentEdgeDilationPerformanceBenchmark =
            _wcsicmp(parameter.first.c_str(), L"smaaCurrentEdgeDilationPerformanceBenchmark") == 0;
        const bool filteredQuarterPerformanceSmoke =
            _wcsicmp(parameter.first.c_str(), L"smaaFilteredQuarterPerformanceSmoke") == 0;
        const bool filteredQuarterPerformanceBenchmark =
            _wcsicmp(parameter.first.c_str(), L"smaaFilteredQuarterPerformanceBenchmark") == 0;
        const bool fullComponentAblationPerformance =
            componentAblationPerformanceSmoke || componentAblationPerformanceBenchmark;
        const bool candidateAblationPerformance =
            candidateAblationPerformanceSmoke || candidateAblationPerformanceBenchmark
            || fullComponentAblationPerformance;
        const bool performanceSmoke = originalPerformanceSmoke || eightCasePerformanceSmoke
            || candidateAblationPerformanceSmoke || componentAblationPerformanceSmoke
            || currentEdgeDilationPerformanceSmoke || filteredQuarterPerformanceSmoke;
        const bool repeatedPerformanceBenchmark = originalPerformanceBenchmark || eightCasePerformanceBenchmark
            || candidateAblationPerformanceBenchmark || componentAblationPerformanceBenchmark
            || currentEdgeDilationPerformanceBenchmark || filteredQuarterPerformanceBenchmark;
        const bool includeAdaptive = eightCasePerformanceSmoke || eightCasePerformanceBenchmark;
        if (performanceSmoke || repeatedPerformanceBenchmark)
        {
            float startTime = 1.0f;
            int warmupFrameCount = repeatedPerformanceBenchmark? 300 : 60;
            int measureFrameCount = repeatedPerformanceBenchmark? 4800 : 120;
            int repeatCount = repeatedPerformanceBenchmark? 3 : 1;
            if (!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if (!(values >> startTime >> warmupFrameCount >> measureFrameCount))
                {
                    VA_LOG_ERROR("Invalid SMAA temporal performance values; expected: <startTimeSeconds> <warmupFrames> <measureFrames> [repeats]");
                    return;
                }
                int parsedRepeatCount = repeatCount;
                if (values >> parsedRepeatCount)
                    repeatCount = parsedRepeatCount;
            }
            startTime = vaMath::Max(0.0f, startTime);
            warmupFrameCount = vaMath::Clamp(warmupFrameCount, 8, 600);
            measureFrameCount = vaMath::Clamp(measureFrameCount, 16, 4800);
            repeatCount = vaMath::Clamp(repeatCount, 1, 9);
            if (repeatedPerformanceBenchmark)
                m_SMAA->SetTemporalCandidateStatisticsReadbackEnabled(false);
            m_autoBench->AddTask(std::make_shared<BenchItemSMAATemporalPerformanceBenchmark>(
                *this, startTime, warmupFrameCount, measureFrameCount, repeatCount,
                includeAdaptive, candidateAblationPerformance,
                fullComponentAblationPerformance,
                currentEdgeDilationPerformanceSmoke
                    || currentEdgeDilationPerformanceBenchmark,
                filteredQuarterPerformanceSmoke
                    || filteredQuarterPerformanceBenchmark));
            m_quitAfterCommandLineCapture = true;
            const char * performanceKind = "Original four-mode";
            if( includeAdaptive )
                performanceKind = "eight-case";
            if( candidateAblationPerformance )
                performanceKind = "candidate-only controlled ablation";
            if( fullComponentAblationPerformance )
                performanceKind = "temporal component ablation";
            if( currentEdgeDilationPerformanceSmoke || currentEdgeDilationPerformanceBenchmark )
                performanceKind = "current-edge 3x3 dilation ablation";
            if( filteredQuarterPerformanceSmoke || filteredQuarterPerformanceBenchmark )
                performanceKind = "filtered-quarter candidate-expansion ablation";
            VA_LOG("Queued SMAA %s %s: start %.3f s, %d repeats, %d warm-up frames, %d measurement frames per run, candidate readback %s",
                performanceKind,
                repeatedPerformanceBenchmark? "repeated performance benchmark" : "performance smoke",
                startTime, repeatCount, warmupFrameCount, measureFrameCount,
                m_SMAA->GetTemporalCandidateStatisticsReadbackEnabled()? "On" : "Off");
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaCandidateReadbackOverheadTest") == 0)
        {
            float startTime = 1.0f;
            int warmupFrameCount = 60;
            int measureFrameCount = 180;
            if (!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if (!(values >> startTime >> warmupFrameCount >> measureFrameCount))
                {
                    VA_LOG_ERROR("Invalid -smaaCandidateReadbackOverheadTest values; expected: <startTimeSeconds> <warmupFrames> <measureFrames>");
                    return;
                }
            }
            startTime = vaMath::Max(0.0f, startTime);
            warmupFrameCount = vaMath::Clamp(warmupFrameCount, 8, 600);
            measureFrameCount = vaMath::Clamp(measureFrameCount, 16, 4800);
            m_autoBench->AddTask(std::make_shared<BenchItemSMAACandidateReadbackOverhead>(
                *this, startTime, warmupFrameCount, measureFrameCount));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA candidate statistics readback overhead smoke: start %.3f s, %d warm-up frames, %d measurement frames",
                startTime, warmupFrameCount, measureFrameCount);
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaCandidatePolicyValidationTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAACandidatePolicy>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA Intel-family candidate policy removal sweep");
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaVarianceClippingTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAAVarianceClipping>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA YCoCg variance-clipping GPU/CPU validation");
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaCatmullRomReferenceTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAACatmullRom>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA Catmull-Rom 5-tap GPU/CPU reference validation");
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaTemporalVelocityTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAATemporalVelocity>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA camera-motion GPU velocity engineering validation");
            return;
        }

        if (_wcsicmp(parameter.first.c_str(), L"smaaTemporalLifecycleTest") == 0)
        {
            m_autoBench->AddTask(std::make_shared<BenchItemValidateSMAATemporalLifecycle>(*this));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA temporal lifecycle engineering validation");
            return;
        }

        if( _wcsicmp( parameter.first.c_str( ),
            L"smaaCameraMotionPreview" ) == 0 )
        {
            wstring sceneToken = L"bistro";
            wstring profileToken = L"yaw-slow-360";
            wstring modeToken = L"O-ET2X-R";
            int repeatCount = 1;
            if( !parameter.second.empty( ) )
            {
                std::wistringstream values( parameter.second );
                if( !(values >> sceneToken >> profileToken) )
                {
                    VA_LOG_ERROR(
                        "Invalid SMAA camera-motion preview values; expected: <bistro|minecraft|powerplant|sanmiguel> <yaw-slow-360|yaw-fast-360|yaw-extreme-360|strafe-fast|yaw-strafe-fast> [O-1X|O-T2X|O-T2X-R|O-ET2X|O-ET2X-R|A-1X|A-T2X|A-T2X-R|A-ET2X|A-ET2X-R] [repeatCount]" );
                    return;
                }
                if( values >> modeToken )
                {
                    int parsedRepeatCount = 1;
                    if( values >> parsedRepeatCount )
                        repeatCount = parsedRepeatCount;
                }
            }

            SceneSelectionType scene = SceneSelectionType::MaxValue;
            SMAACameraMotionProfile profile = SMAACameraMotionProfile::MaxValue;
            AAType mode = AAType::SMAA_O_ET2X_R;
            string semanticID;
            if( !TryParseSMAACameraMotionScene( sceneToken, scene ) )
            {
                VA_LOG_ERROR(
                    "Invalid SMAA camera-motion preview scene; expected bistro, minecraft, powerplant, or sanmiguel" );
                return;
            }
            if( scene == SceneSelectionType::PowerPlantThinGeometry && !HasPowerPlantPreview() )
            {
                VA_LOG_ERROR("Power Plant camera-motion preview requires -smaaPowerPlantPreviewCache <absolute .smaapp path>");
                return;
            }
            if( scene == SceneSelectionType::SanMiguelTextured && !HasSanMiguelScene() )
            {
                VA_LOG_ERROR("San Miguel camera-motion preview requires -smaaSanMiguelCache <absolute .smaasm path>");
                return;
            }
            if( !TryParseSMAACameraMotionProfile( profileToken, profile ) )
            {
                VA_LOG_ERROR(
                    "Invalid SMAA camera-motion preview profile; expected yaw-slow-360, yaw-fast-360, yaw-extreme-360, strafe-fast, or yaw-strafe-fast" );
                return;
            }
            if( !TryParseSMAAResearchMode( modeToken, mode, semanticID ) )
            {
                VA_LOG_ERROR(
                    "Invalid SMAA camera-motion preview mode; use a semantic O/A 1X/T2X/ET2X ID" );
                return;
            }
            repeatCount = vaMath::Clamp( repeatCount, 1, 20 );

            m_autoBench->AddTask(
                std::make_shared<BenchItemPreviewSMAACameraMotion>(
                    *this, scene, profile, mode, semanticID, repeatCount ) );
            m_quitAfterCommandLineCapture = true;
            VA_LOG(
                "Queued real-time SMAA camera-motion preview: scene=%s, profile=%s, mode=%s, repeats=%d, PNG capture=off",
                GetSMAACameraMotionSceneName( scene ),
                GetSMAACameraMotionProfileName( profile ),
                semanticID.c_str( ), repeatCount );
            return;
        }

        const bool cameraMotionOriginalFive =
            _wcsicmp( parameter.first.c_str( ),
                L"smaaCameraMotionOriginalFiveCapture" ) == 0;
        const bool cameraMotionEightCase =
            _wcsicmp( parameter.first.c_str( ),
                L"smaaCameraMotionEightCaseCapture" ) == 0;
        const bool cameraMotionReference =
            _wcsicmp( parameter.first.c_str( ),
                L"smaaCameraMotionReferenceCapture" ) == 0;
        const bool realSceneTemporalRetention =
            _wcsicmp( parameter.first.c_str( ),
                L"smaaRealSceneTemporalRetentionCapture" ) == 0;
        const bool currentEdgeDilationAblation =
            _wcsicmp( parameter.first.c_str( ),
                L"smaaCurrentEdgeDilationAblationCapture" ) == 0;
        const bool filteredQuarterAblation =
            _wcsicmp( parameter.first.c_str( ),
                L"smaaFilteredQuarterAblationCapture" ) == 0;
        if( cameraMotionOriginalFive || cameraMotionEightCase || cameraMotionReference
            || realSceneTemporalRetention || currentEdgeDilationAblation
            || filteredQuarterAblation )
        {
            wstring sceneToken = L"bistro";
            wstring profileToken = L"yaw-fast-360";
            int firstProfileFrame = 0;
            int captureFrameCount = 0;
            int warmupFrameCount = 60;
            if( !parameter.second.empty( ) )
            {
                std::wistringstream values( parameter.second );
                if( !(values >> sceneToken >> profileToken) )
                {
                    VA_LOG_ERROR(
                        "Invalid SMAA camera-motion capture values; expected: <bistro|minecraft|powerplant|sanmiguel> <yaw-slow-360|yaw-fast-360|yaw-extreme-360|strafe-fast|yaw-strafe-fast> [firstProfileFrame] [captureFrames] [warmupFrames]" );
                    return;
                }
                int parsedValue = 0;
                if( values >> parsedValue )
                    firstProfileFrame = parsedValue;
                if( values >> parsedValue )
                    captureFrameCount = parsedValue;
                if( values >> parsedValue )
                    warmupFrameCount = parsedValue;
            }

            SceneSelectionType scene = SceneSelectionType::MaxValue;
            if( !TryParseSMAACameraMotionScene( sceneToken, scene ) )
            {
                VA_LOG_ERROR(
                    "Invalid SMAA camera-motion scene; expected bistro, minecraft, powerplant, or sanmiguel" );
                return;
            }
            if( scene == SceneSelectionType::PowerPlantThinGeometry && !HasPowerPlantPreview() )
            {
                VA_LOG_ERROR("Power Plant camera-motion capture requires -smaaPowerPlantPreviewCache <absolute .smaapp path>");
                return;
            }
            if( scene == SceneSelectionType::SanMiguelTextured && !HasSanMiguelScene() )
            {
                VA_LOG_ERROR("San Miguel camera-motion capture requires -smaaSanMiguelCache <absolute .smaasm path>");
                return;
            }
            if( realSceneTemporalRetention
                && scene == SceneSelectionType::PowerPlantThinGeometry )
            {
                VA_LOG_ERROR(
                    "Real-scene temporal-retention capture excludes the incomplete Power Plant renderer; use bistro, minecraft, or sanmiguel" );
                return;
            }
            if( (currentEdgeDilationAblation || filteredQuarterAblation)
                && scene == SceneSelectionType::PowerPlantThinGeometry )
            {
                VA_LOG_ERROR(
                    "Candidate-expansion capture excludes the incomplete Power Plant renderer; use bistro, minecraft, or sanmiguel" );
                return;
            }

            SMAACameraMotionProfile profile = SMAACameraMotionProfile::MaxValue;
            if( _wcsicmp( profileToken.c_str( ), L"yaw-slow-360" ) == 0 )
                profile = SMAACameraMotionProfile::YawSlow360;
            else if( _wcsicmp( profileToken.c_str( ), L"yaw-fast-360" ) == 0 )
                profile = SMAACameraMotionProfile::YawFast360;
            else if( _wcsicmp( profileToken.c_str( ), L"yaw-extreme-360" ) == 0 )
                profile = SMAACameraMotionProfile::YawExtreme360;
            else if( _wcsicmp( profileToken.c_str( ), L"strafe-fast" ) == 0 )
                profile = SMAACameraMotionProfile::StrafeFast;
            else if( _wcsicmp( profileToken.c_str( ), L"yaw-strafe-fast" ) == 0 )
                profile = SMAACameraMotionProfile::YawStrafeFast;
            else
            {
                VA_LOG_ERROR(
                    "Invalid SMAA camera-motion profile; expected yaw-slow-360, yaw-fast-360, yaw-extreme-360, strafe-fast, or yaw-strafe-fast" );
                return;
            }

            const int profileFrameCount =
                GetSMAACameraMotionProfileFrameCount( profile );
            firstProfileFrame = vaMath::Clamp(
                firstProfileFrame, 0, profileFrameCount - 1 );
            const int remainingFrames = profileFrameCount - firstProfileFrame;
            if( captureFrameCount <= 0 )
                captureFrameCount = remainingFrames;
            captureFrameCount = vaMath::Clamp(
                captureFrameCount, 1, remainingFrames );
            warmupFrameCount = vaMath::Clamp( warmupFrameCount, 0, 600 );

            m_autoBench->AddTask( std::make_shared<BenchItemRecordSMAACameraMotion>(
                *this, scene, profile, firstProfileFrame, captureFrameCount,
                warmupFrameCount, cameraMotionReference, cameraMotionEightCase,
                realSceneTemporalRetention, currentEdgeDilationAblation,
                filteredQuarterAblation ) );
            m_quitAfterCommandLineCapture = true;
            VA_LOG(
                "Queued SMAA camera-motion %s: scene=%s, profile=%s, profile frames [%d,%d], warm-up=%d",
                cameraMotionReference? "supersample reference capture" :
                    (filteredQuarterAblation? "filtered-quarter candidate-expansion ablation capture" :
                    (currentEdgeDilationAblation? "current-edge 3x3 dilation ablation capture" :
                    (realSceneTemporalRetention? "real-scene temporal-retention five-way capture" :
                    (cameraMotionEightCase? "final eight-case plus O/A 1X controls capture" :
                        "Original five-way capture")))),
                GetSMAACameraMotionSceneName( scene ),
                GetSMAACameraMotionProfileName( profile ), firstProfileFrame,
                firstProfileFrame + captureFrameCount - 1, warmupFrameCount );
            return;
        }

        if( _wcsicmp( parameter.first.c_str( ),
            L"smaaSupersampleStressReferenceCapture" ) == 0 )
        {
            wstring scenarioToken = L"object-motion";
            int frameCount = 240;
            int warmupFrameCount = 10;
            if( !parameter.second.empty( ) )
            {
                std::wistringstream values( parameter.second );
                if( !(values >> scenarioToken >> frameCount >> warmupFrameCount) )
                {
                    VA_LOG_ERROR(
                        "Invalid SMAA supersample stress reference values; expected: <thin-lines|object-motion|combined> <captureFrames> <warmupFrames>" );
                    return;
                }
            }

            SMAATemporalStressScenario scenario =
                SMAATemporalStressScenario::MaxValue;
            if( _wcsicmp( scenarioToken.c_str( ), L"thin-lines" ) == 0 )
                scenario = SMAATemporalStressScenario::ThinLinesCameraPan;
            else if( _wcsicmp( scenarioToken.c_str( ), L"object-motion" ) == 0 )
                scenario = SMAATemporalStressScenario::ObjectMotionDisocclusion;
            else if( _wcsicmp( scenarioToken.c_str( ), L"combined" ) == 0 )
                scenario = SMAATemporalStressScenario::CombinedCameraAndObjectMotion;
            else
            {
                VA_LOG_ERROR(
                    "Invalid SMAA supersample stress reference scenario; expected thin-lines, object-motion, or combined" );
                return;
            }

            frameCount = vaMath::Clamp( frameCount, 1, 1800 );
            warmupFrameCount = vaMath::Clamp( warmupFrameCount, 0, 600 );
            m_autoBench->AddTask(
                std::make_shared<BenchItemRecordSMAASupersampleStressReference>(
                    *this, scenario, frameCount, warmupFrameCount ) );
            m_quitAfterCommandLineCapture = true;
            VA_LOG(
                "Queued SMAA supersample stress reference '%s': %d capture frames, %d warm-up frames",
                GetSMAATemporalStressScenarioName( scenario ),
                frameCount, warmupFrameCount );
            return;
        }

        const bool candidatePolicyJitterAblationCapture =
            _wcsicmp(parameter.first.c_str(), L"smaaCandidatePolicyJitterAblationCapture") == 0;
        const bool candidateJitterIsolationCapture =
            _wcsicmp(parameter.first.c_str(), L"smaaCandidateJitterIsolationCapture") == 0;
        const bool hybridResolveAblationCapture =
            _wcsicmp(parameter.first.c_str(), L"smaaHybridResolveAblationCapture") == 0;
        const bool candidateOnlyAblationCapture =
            _wcsicmp(parameter.first.c_str(), L"smaaCandidateOnlyAblationCapture") == 0;
        const bool temporalComponentAblationCapture =
            _wcsicmp(parameter.first.c_str(), L"smaaTemporalComponentAblationCapture") == 0;
        if (candidatePolicyJitterAblationCapture || candidateJitterIsolationCapture
            || hybridResolveAblationCapture
            || candidateOnlyAblationCapture || temporalComponentAblationCapture)
        {
            wstring scenarioToken = L"object-motion";
            int frameCount = 180;
            int warmupFrameCount = 60;
            if(!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if(!(values >> scenarioToken >> frameCount >> warmupFrameCount))
                {
                    VA_LOG_ERROR("Invalid SMAA candidate ablation capture values; expected: <thin-lines|object-motion|combined> <captureFrames> <warmupFrames>");
                    return;
                }
            }

            SMAATemporalStressScenario scenario = SMAATemporalStressScenario::MaxValue;
            if(_wcsicmp(scenarioToken.c_str(), L"thin-lines") == 0)
                scenario = SMAATemporalStressScenario::ThinLinesCameraPan;
            else if(_wcsicmp(scenarioToken.c_str(), L"object-motion") == 0)
                scenario = SMAATemporalStressScenario::ObjectMotionDisocclusion;
            else if(_wcsicmp(scenarioToken.c_str(), L"combined") == 0)
                scenario = SMAATemporalStressScenario::CombinedCameraAndObjectMotion;
            else
            {
                VA_LOG_ERROR("Invalid SMAA candidate ablation scenario; expected thin-lines, object-motion, or combined");
                return;
            }

            frameCount = vaMath::Clamp(frameCount, 1, 1800);
            warmupFrameCount = vaMath::Clamp(warmupFrameCount, 1, 600);
            if( candidatePolicyJitterAblationCapture )
                m_autoBench->AddTask(
                    std::make_shared<BenchItemRecordSMAACandidatePolicyJitterAblation>(
                        *this, scenario, frameCount, warmupFrameCount ) );
            else
                m_autoBench->AddTask(
                    std::make_shared<BenchItemRecordSMAACandidateOnlyAblation>(
                        *this, scenario, frameCount, warmupFrameCount,
                        temporalComponentAblationCapture,
                        candidateJitterIsolationCapture,
                        hybridResolveAblationCapture ) );
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA %s controlled ablation '%s': %d capture frames, %d warm-up frames",
                candidatePolicyJitterAblationCapture? "candidate-policy jitter" :
                    (hybridResolveAblationCapture? "hybrid resolve" :
                        (candidateJitterIsolationCapture? "candidate jitter isolation" :
                            (temporalComponentAblationCapture? "temporal component" : "candidate-only"))),
                GetSMAATemporalStressScenarioName(scenario),
                frameCount, warmupFrameCount);
            return;
        }

        const bool oneXStressControls =
            _wcsicmp(parameter.first.c_str(), L"smaaOneXStressCapture") == 0;
        if (oneXStressControls
            || _wcsicmp(parameter.first.c_str(), L"smaaEightCaseStressCapture") == 0)
        {
            wstring scenarioToken = L"object-motion";
            int frameCount = 180;
            int warmupFrameCount = 60;
            if(!parameter.second.empty())
            {
                std::wistringstream values(parameter.second);
                if(!(values >> scenarioToken >> frameCount >> warmupFrameCount))
                {
                    VA_LOG_ERROR("Invalid SMAA stress capture values; expected: <thin-lines|object-motion|combined> <captureFrames> <warmupFrames>");
                    return;
                }
            }

            SMAATemporalStressScenario scenario = SMAATemporalStressScenario::MaxValue;
            if(_wcsicmp(scenarioToken.c_str(), L"thin-lines") == 0)
                scenario = SMAATemporalStressScenario::ThinLinesCameraPan;
            else if(_wcsicmp(scenarioToken.c_str(), L"object-motion") == 0)
                scenario = SMAATemporalStressScenario::ObjectMotionDisocclusion;
            else if(_wcsicmp(scenarioToken.c_str(), L"combined") == 0)
                scenario = SMAATemporalStressScenario::CombinedCameraAndObjectMotion;
            else
            {
                VA_LOG_ERROR("Invalid SMAA temporal stress scenario; expected thin-lines, object-motion, or combined");
                return;
            }

            frameCount = vaMath::Clamp(frameCount, 1, 1800);
            warmupFrameCount = vaMath::Clamp(warmupFrameCount, 1, 600);
            m_autoBench->AddTask(
                std::make_shared<BenchItemRecordSMAATemporalStressMatrix>(
                    *this, scenario, frameCount, warmupFrameCount,
                    oneXStressControls));
            m_quitAfterCommandLineCapture = true;
            VA_LOG("Queued SMAA %s '%s' temporal stress capture: %d capture frames, %d warm-up frames",
                oneXStressControls? "1X controls" : "eight-case",
                GetSMAATemporalStressScenarioName(scenario),
                frameCount, warmupFrameCount);
            return;
        }

        const bool originalFourCapture = _wcsicmp(parameter.first.c_str(), L"smaaOriginalFourCapture") == 0;
        const bool eightCaseCapture = _wcsicmp(parameter.first.c_str(), L"smaaEightCaseCapture") == 0;
        const bool legacyPairCaptureAlias = _wcsicmp(parameter.first.c_str(), L"smaaTemporalPairCapture") == 0;
        if (!originalFourCapture && !eightCaseCapture && !legacyPairCaptureAlias)
            continue;

        float startTime = m_temporalComparisonStartTime;
        int frameCount = m_temporalComparisonFrameCount;
        int warmupFrameCount = m_temporalComparisonWarmupFrames;
        if (!parameter.second.empty())
        {
            std::wistringstream values(parameter.second);
            if (!(values >> startTime >> frameCount >> warmupFrameCount))
            {
                VA_LOG_ERROR("Invalid SMAA temporal capture values; expected: <startTimeSeconds> <captureFrames> <warmupFrames>");
                return;
            }
        }

        frameCount = vaMath::Clamp(frameCount, 1, 1800);
        warmupFrameCount = vaMath::Clamp(warmupFrameCount, 0, 600);
        startTime = vaMath::Max(0.0f, startTime);
        m_autoBench->AddTask(std::make_shared<BenchItemRecordSMAATemporalMatrix>(
            *this, startTime, frameCount, warmupFrameCount, eightCaseCapture));
        m_quitAfterCommandLineCapture = true;
        VA_LOG("Queued SMAA %s temporal capture: start %.3f s, %d capture frames, %d warm-up frames",
            eightCaseCapture? "eight-case" : "Original four-mode", startTime, frameCount, warmupFrameCount);
        return;
    }
}

bool CMAA2Sample::LoadPowerPlantPreviewCache(const wstring& cachePath)
{
    static const char expectedMagic[8] = { 'S', 'M', 'A', 'A', 'P', 'P', '1', '\0' };
    static const uint32 expectedVersion = 1;
    static const uint32 maximumNameLength = 1024;
    static const uint32 maximumChunkCount = 256;
    static const uint64 maximumVertexCount = 25ull * 1000ull * 1000ull;
    static const uint64 maximumIndexCount = 75ull * 1000ull * 1000ull;

    vaFileStream stream;
    if(!stream.Open(cachePath, FileCreationMode::Open, FileAccessMode::Read))
    {
        VA_LOG_ERROR(L"Unable to open Power Plant preview cache '%s'", cachePath.c_str());
        return false;
    }
    auto readExact = [&stream](void* destination, int64 byteCount)
    {
        int64 bytesRead = 0;
        return stream.Read(destination, byteCount, &bytesRead) && bytesRead == byteCount;
    };

    char magic[8] = {};
    uint32 version = 0;
    uint32 sectionNameLength = 0;
    uint32 chunkCount = 0;
    uint32 reserved = 0;
    uint64 declaredVertexCount = 0;
    uint64 declaredIndexCount = 0;
    float declaredBounds[6] = {};
    if(!readExact(magic, sizeof(magic))
        || !stream.ReadValue(version)
        || !stream.ReadValue(sectionNameLength)
        || !stream.ReadValue(chunkCount)
        || !stream.ReadValue(reserved)
        || !stream.ReadValue(declaredVertexCount)
        || !stream.ReadValue(declaredIndexCount)
        || !readExact(declaredBounds, sizeof(declaredBounds)))
    {
        VA_LOG_ERROR(L"Truncated Power Plant cache header in '%s'", cachePath.c_str());
        return false;
    }
    if(std::memcmp(magic, expectedMagic, sizeof(magic)) != 0
        || version != expectedVersion || reserved != 0
        || sectionNameLength == 0 || sectionNameLength > maximumNameLength
        || chunkCount == 0 || chunkCount > maximumChunkCount
        || declaredVertexCount == 0 || declaredVertexCount > maximumVertexCount
        || declaredIndexCount == 0 || declaredIndexCount > maximumIndexCount
        || (declaredIndexCount % 3) != 0)
    {
        VA_LOG_ERROR(L"Invalid Power Plant cache header in '%s'", cachePath.c_str());
        return false;
    }
    for(float value : declaredBounds)
    {
        if(!std::isfinite(value))
        {
            VA_LOG_ERROR(L"Non-finite Power Plant cache bounds in '%s'", cachePath.c_str());
            return false;
        }
    }

    string sectionName(sectionNameLength, '\0');
    if(!readExact(&sectionName[0], sectionNameLength))
    {
        VA_LOG_ERROR(L"Truncated Power Plant section name in '%s'", cachePath.c_str());
        return false;
    }

    shared_ptr<vaScene> scene = m_scenes[(int32)SceneSelectionType::PowerPlantThinGeometry];
    scene->Clear();
    m_powerPlantPreviewMeshes.clear();
    m_powerPlantPreviewMaterials.clear();
    scene->Name() = "UNC Power Plant " + sectionName + " (external research scene)";
    scene->SetSkybox(GetRenderDevice(), "Media\\sky_cube.dds", vaMatrix3x3::Identity, 0.012f);
    scene->Lights().push_back(std::make_shared<vaLight>(
        vaLight::MakeAmbient("PowerPlantAmbient", vaVector3(0.5f, 0.5f, 0.5f))));
    scene->Lights().push_back(std::make_shared<vaLight>(
        vaLight::MakeDirectional("PowerPlantDirectional", vaVector3(0.95f, 0.95f, 0.9f),
            vaVector3(-0.35f, 0.4f, -1.0f).Normalized())));

    uint64 loadedVertexCount = 0;
    uint64 loadedIndexCount = 0;
    for(uint32 chunkIndex = 0; chunkIndex < chunkCount; chunkIndex++)
    {
        uint32 materialNameLength = 0;
        float albedo[4] = {};
        uint32 vertexCount = 0;
        uint32 indexCount = 0;
        if(!stream.ReadValue(materialNameLength)
            || !readExact(albedo, sizeof(albedo))
            || !stream.ReadValue(vertexCount)
            || !stream.ReadValue(indexCount)
            || materialNameLength == 0 || materialNameLength > maximumNameLength
            || vertexCount == 0 || indexCount == 0 || (indexCount % 3) != 0
            || loadedVertexCount + vertexCount > declaredVertexCount
            || loadedIndexCount + indexCount > declaredIndexCount)
        {
            VA_LOG_ERROR(L"Invalid Power Plant chunk %u in '%s'", chunkIndex, cachePath.c_str());
            scene->Clear();
            m_powerPlantPreviewMeshes.clear();
            m_powerPlantPreviewMaterials.clear();
            return false;
        }
        for(float value : albedo)
        {
            if(!std::isfinite(value))
            {
                VA_LOG_ERROR(L"Non-finite Power Plant material in '%s'", cachePath.c_str());
                return false;
            }
        }

        string materialName(materialNameLength, '\0');
        vector<float> positionValues((size_t)vertexCount * 3);
        vector<float> normalValues((size_t)vertexCount * 3);
        vector<uint32> indices(indexCount);
        if(!readExact(&materialName[0], materialNameLength)
            || !readExact(positionValues.data(), (int64)positionValues.size() * sizeof(float))
            || !readExact(normalValues.data(), (int64)normalValues.size() * sizeof(float))
            || !readExact(indices.data(), (int64)indices.size() * sizeof(uint32)))
        {
            VA_LOG_ERROR(L"Truncated Power Plant chunk %u in '%s'", chunkIndex, cachePath.c_str());
            return false;
        }

        vector<vaVector3> vertices(vertexCount);
        vector<vaVector3> normals(vertexCount);
        vector<vaVector2> texcoords0(vertexCount, vaVector2(0.0f, 0.0f));
        vector<vaVector2> texcoords1(vertexCount, vaVector2(0.0f, 0.0f));
        for(uint32 vertexIndex = 0; vertexIndex < vertexCount; vertexIndex++)
        {
            const size_t component = (size_t)vertexIndex * 3;
            vertices[vertexIndex] = vaVector3(positionValues[component],
                positionValues[component + 1], positionValues[component + 2]);
            normals[vertexIndex] = vaVector3(normalValues[component],
                normalValues[component + 1], normalValues[component + 2]).Normalized();
        }
        for(uint32 index : indices)
        {
            if(index >= vertexCount)
            {
                VA_LOG_ERROR(L"Out-of-range Power Plant index in chunk %u of '%s'",
                    chunkIndex, cachePath.c_str());
                return false;
            }
        }

        shared_ptr<vaRenderMaterial> material =
            GetRenderDevice().GetMaterialManager().CreateRenderMaterial(vaCore::GUIDCreate());
        material->InitializeDefaultMaterial();
        const int albedoIndex = material->FindInputByName("Albedo");
        if(albedoIndex < 0)
        {
            VA_LOG_ERROR("Power Plant preview material has no Albedo input");
            return false;
        }
        vaRenderMaterial::MaterialInput albedoInput = material->GetInputs()[albedoIndex];
        albedoInput.Value = vaRenderMaterial::MaterialInput::ValueVar(
            vaVector4(albedo[0], albedo[1], albedo[2], 1.0f));
        material->SetInput(albedoIndex, albedoInput);
        vaRenderMaterial::MaterialSettings materialSettings = material->GetMaterialSettings();
        materialSettings.CastShadows = false;
        materialSettings.ReceiveShadows = false;
        materialSettings.FaceCull = vaFaceCull::None;
        material->SetMaterialSettings(materialSettings);

        shared_ptr<vaRenderMesh> mesh = vaRenderMesh::Create(
            GetRenderDevice(), vaMatrix4x4::Identity, vertices, normals,
            texcoords0, texcoords1, indices, vaWindingOrder::CounterClockwise);
        vaRenderMesh::SubPart part = mesh->GetPart();
        part.CachedMaterialRef = material;
        part.MaterialID = material->UIDObject_GetUID();
        mesh->SetPart(part);

        shared_ptr<vaSceneObject> object = scene->CreateObject(
            "PowerPlant_" + sectionName + "_" + materialName, vaMatrix4x4::Identity);
        object->AddRenderMeshRef(mesh);
        m_powerPlantPreviewMeshes.push_back(mesh);
        m_powerPlantPreviewMaterials.push_back(material);
        loadedVertexCount += vertexCount;
        loadedIndexCount += indexCount;
    }

    if(loadedVertexCount != declaredVertexCount || loadedIndexCount != declaredIndexCount
        || stream.GetPosition() != stream.GetLength())
    {
        VA_LOG_ERROR(L"Power Plant cache totals or trailing bytes mismatch in '%s'", cachePath.c_str());
        scene->Clear();
        m_powerPlantPreviewMeshes.clear();
        m_powerPlantPreviewMaterials.clear();
        return false;
    }

    VA_LOG(L"Loaded UNC Power Plant preview cache '%s': section=%S, chunks=%u, vertices=%llu, triangles=%llu",
        cachePath.c_str(), sectionName.c_str(), chunkCount,
        (unsigned long long)loadedVertexCount,
        (unsigned long long)(loadedIndexCount / 3));
    return true;
}

bool CMAA2Sample::LoadSanMiguelTexturedScene(const wstring& cachePath)
{
    static const char expectedMagic[8] = { 'S', 'M', 'A', 'A', 'S', 'M', '1', '\0' };
    static const uint32 expectedVersion = 1;
    static const uint32 maximumStringLength = 4096;
    static const uint32 maximumMaterialCount = 2048;
    static const uint32 maximumChunkCount = 8192;
    static const uint64 maximumVertexCount = 50ull * 1000ull * 1000ull;
    static const uint64 maximumIndexCount = 150ull * 1000ull * 1000ull;

    vaFileStream stream;
    if(!stream.Open(cachePath, FileCreationMode::Open, FileAccessMode::Read))
    {
        VA_LOG_ERROR(L"Unable to open San Miguel cache '%s'", cachePath.c_str());
        return false;
    }
    wstring directory;
    wstring extension;
    vaFileTools::SplitPath(cachePath, &directory, nullptr, &extension);
    if(_wcsicmp(extension.c_str(), L".smaasm") != 0)
    {
        VA_LOG_ERROR(L"San Miguel cache must use .smaasm, got '%s'", cachePath.c_str());
        return false;
    }

    auto readExact = [&stream](void* destination, int64 byteCount)
    {
        int64 bytesRead = 0;
        return stream.Read(destination, byteCount, &bytesRead) && bytesRead == byteCount;
    };
    char magic[8] = {};
    uint32 version = 0;
    uint32 materialCount = 0;
    uint32 chunkCount = 0;
    uint32 reserved = 0;
    uint64 declaredVertexCount = 0;
    uint64 declaredIndexCount = 0;
    float declaredBounds[6] = {};
    if(!readExact(magic, sizeof(magic))
        || !stream.ReadValue(version)
        || !stream.ReadValue(materialCount)
        || !stream.ReadValue(chunkCount)
        || !stream.ReadValue(reserved)
        || !stream.ReadValue(declaredVertexCount)
        || !stream.ReadValue(declaredIndexCount)
        || !readExact(declaredBounds, sizeof(declaredBounds))
        || std::memcmp(magic, expectedMagic, sizeof(magic)) != 0
        || version != expectedVersion || reserved != 0
        || materialCount == 0 || materialCount > maximumMaterialCount
        || chunkCount == 0 || chunkCount > maximumChunkCount
        || declaredVertexCount == 0 || declaredVertexCount > maximumVertexCount
        || declaredIndexCount == 0 || declaredIndexCount > maximumIndexCount
        || (declaredIndexCount % 3) != 0)
    {
        VA_LOG_ERROR(L"Invalid San Miguel cache header in '%s'", cachePath.c_str());
        return false;
    }
    for(float value : declaredBounds)
    {
        if(!std::isfinite(value))
        {
            VA_LOG_ERROR(L"Non-finite San Miguel cache bounds in '%s'", cachePath.c_str());
            return false;
        }
    }

    shared_ptr<vaScene> scene = m_scenes[(int32)SceneSelectionType::SanMiguelTextured];
    scene->Clear();
    m_sanMiguelPreviewMeshes.clear();
    m_sanMiguelPreviewMaterials.clear();
    m_sanMiguelPreviewTextures.clear();
    scene->Name() = "San Miguel 2.1 (external textured research scene)";

    for(uint32 materialIndex = 0; materialIndex < materialCount; materialIndex++)
    {
        uint32 materialNameLength = 0;
        uint32 texturePathLength = 0;
        uint32 flags = 0;
        uint32 materialReserved = 0;
        float albedo[4] = {};
        float specularPower = 0.0f;
        if(!stream.ReadValue(materialNameLength)
            || !stream.ReadValue(texturePathLength)
            || !stream.ReadValue(flags)
            || !stream.ReadValue(materialReserved)
            || !readExact(albedo, sizeof(albedo))
            || !stream.ReadValue(specularPower)
            || materialNameLength == 0 || materialNameLength > maximumStringLength
            || texturePathLength > maximumStringLength
            || flags > 1 || materialReserved != 0 || !std::isfinite(specularPower))
        {
            VA_LOG_ERROR(L"Invalid San Miguel material %u in '%s'",
                materialIndex, cachePath.c_str());
            return false;
        }
        for(float value : albedo)
            if(!std::isfinite(value))
                return false;

        string materialName(materialNameLength, '\0');
        string texturePath(texturePathLength, '\0');
        if(!readExact(&materialName[0], materialNameLength)
            || (texturePathLength > 0
                && !readExact(&texturePath[0], texturePathLength))
            || texturePath.find("..") != string::npos
            || texturePath.find(':') != string::npos
            || (!texturePath.empty() && (texturePath[0] == '/' || texturePath[0] == '\\')))
        {
            VA_LOG_ERROR(L"Invalid San Miguel material strings in '%s'", cachePath.c_str());
            return false;
        }

        shared_ptr<vaRenderMaterial> material =
            GetRenderDevice().GetMaterialManager().CreateRenderMaterial(vaCore::GUIDCreate());
        material->InitializeDefaultMaterial();
        const vaVector4 albedoValue(albedo[0], albedo[1], albedo[2], albedo[3]);
        if(texturePath.empty())
        {
            const int albedoIndex = material->FindInputByName("Albedo");
            if(albedoIndex < 0)
                return false;
            vaRenderMaterial::MaterialInput input = material->GetInputs()[albedoIndex];
            input.Value = vaRenderMaterial::MaterialInput::ValueVar(albedoValue);
            material->SetInput(albedoIndex, input);
        }
        else
        {
            const wstring fullTexturePath = directory
                + vaStringTools::SimpleWiden(texturePath);
            shared_ptr<vaTexture> texture = vaTexture::CreateFromImageFile(
                GetRenderDevice(), fullTexturePath,
                vaTextureLoadFlags::PresumeDataIsSRGB,
                vaResourceBindSupportFlags::ShaderResource,
                vaTextureContentsType::GenericColor);
            if(texture == nullptr)
            {
                VA_LOG_ERROR(L"Unable to load San Miguel texture '%s'", fullTexturePath.c_str());
                return false;
            }
            // Texture-backed material inputs resolve their GUID through the
            // global asset registrar. Unlike textures loaded through an asset
            // pack, direct image-file textures are not registered for us.
            if(!texture->UIDObject_IsTracked() && !texture->UIDObject_Track())
            {
                VA_LOG_ERROR(L"Unable to register San Miguel texture '%s'", fullTexturePath.c_str());
                return false;
            }
            material->SetInputByName(vaRenderMaterial::MaterialInput(
                "Albedo", vaRenderMaterial::MaterialInput::InputType::Color4,
                texture->UIDObject_GetUID(), 0,
                vaRenderMaterial::MaterialInput::TextureSamplerType::AnisotropicWrap,
                albedoValue), true);
            m_sanMiguelPreviewTextures.push_back(texture);
        }
        vaRenderMaterial::MaterialSettings materialSettings = material->GetMaterialSettings();
        materialSettings.AlphaTest = (flags & 1) != 0;
        materialSettings.Transparent = false;
        materialSettings.FaceCull = materialSettings.AlphaTest? vaFaceCull::None : vaFaceCull::Back;
        materialSettings.CastShadows = false;
        materialSettings.ReceiveShadows = false;
        material->SetMaterialSettings(materialSettings);
        m_sanMiguelPreviewMaterials.push_back(material);
    }

    uint64 loadedVertexCount = 0;
    uint64 loadedIndexCount = 0;
    for(uint32 chunkIndex = 0; chunkIndex < chunkCount; chunkIndex++)
    {
        uint32 objectNameLength = 0;
        uint32 materialIndex = 0;
        uint32 vertexCount = 0;
        uint32 indexCount = 0;
        if(!stream.ReadValue(objectNameLength)
            || !stream.ReadValue(materialIndex)
            || !stream.ReadValue(vertexCount)
            || !stream.ReadValue(indexCount)
            || objectNameLength == 0 || objectNameLength > maximumStringLength
            || materialIndex >= materialCount || vertexCount == 0
            || indexCount == 0 || (indexCount % 3) != 0
            || loadedVertexCount + vertexCount > declaredVertexCount
            || loadedIndexCount + indexCount > declaredIndexCount)
        {
            VA_LOG_ERROR(L"Invalid San Miguel chunk %u in '%s'", chunkIndex, cachePath.c_str());
            return false;
        }
        string objectName(objectNameLength, '\0');
        vector<float> positionValues((size_t)vertexCount * 3);
        vector<float> normalValues((size_t)vertexCount * 3);
        vector<float> textureCoordinateValues((size_t)vertexCount * 2);
        vector<uint32> indices(indexCount);
        if(!readExact(&objectName[0], objectNameLength)
            || !readExact(positionValues.data(), (int64)positionValues.size() * sizeof(float))
            || !readExact(normalValues.data(), (int64)normalValues.size() * sizeof(float))
            || !readExact(textureCoordinateValues.data(),
                (int64)textureCoordinateValues.size() * sizeof(float))
            || !readExact(indices.data(), (int64)indices.size() * sizeof(uint32)))
        {
            VA_LOG_ERROR(L"Truncated San Miguel chunk %u in '%s'", chunkIndex, cachePath.c_str());
            return false;
        }

        vector<vaVector3> vertices(vertexCount);
        vector<vaVector3> normals(vertexCount);
        vector<vaVector2> texcoords0(vertexCount);
        vector<vaVector2> texcoords1(vertexCount, vaVector2(0.0f, 0.0f));
        for(uint32 vertexIndex = 0; vertexIndex < vertexCount; vertexIndex++)
        {
            const size_t component3 = (size_t)vertexIndex * 3;
            const size_t component2 = (size_t)vertexIndex * 2;
            vertices[vertexIndex] = vaVector3(positionValues[component3],
                positionValues[component3 + 1], positionValues[component3 + 2]);
            normals[vertexIndex] = vaVector3(normalValues[component3],
                normalValues[component3 + 1], normalValues[component3 + 2]).Normalized();
            texcoords0[vertexIndex] = vaVector2(textureCoordinateValues[component2],
                textureCoordinateValues[component2 + 1]);
        }
        for(uint32 index : indices)
            if(index >= vertexCount)
                return false;

        shared_ptr<vaRenderMesh> mesh = vaRenderMesh::Create(
            GetRenderDevice(), vaMatrix4x4::Identity, vertices, normals,
            texcoords0, texcoords1, indices, vaWindingOrder::CounterClockwise);
        vaRenderMesh::SubPart part = mesh->GetPart();
        const shared_ptr<vaRenderMaterial>& material =
            m_sanMiguelPreviewMaterials[materialIndex];
        part.CachedMaterialRef = material;
        part.MaterialID = material->UIDObject_GetUID();
        mesh->SetPart(part);
        shared_ptr<vaSceneObject> object = scene->CreateObject(
            "SanMiguel_" + objectName + "_" + std::to_string(chunkIndex),
            vaMatrix4x4::Identity);
        object->AddRenderMeshRef(mesh);
        m_sanMiguelPreviewMeshes.push_back(mesh);
        loadedVertexCount += vertexCount;
        loadedIndexCount += indexCount;
    }

    if(loadedVertexCount != declaredVertexCount || loadedIndexCount != declaredIndexCount
        || stream.GetPosition() != stream.GetLength())
    {
        VA_LOG_ERROR(L"San Miguel cache totals or trailing bytes mismatch in '%s'", cachePath.c_str());
        return false;
    }

    scene->SetSkybox(GetRenderDevice(), "Media\\sky_cube.dds",
        vaMatrix3x3::Identity, 0.025f);
    scene->Lights().push_back(std::make_shared<vaLight>(
        vaLight::MakeAmbient("SanMiguelAmbient", vaVector3(0.32f, 0.32f, 0.32f))));
    scene->Lights().push_back(std::make_shared<vaLight>(
        vaLight::MakeDirectional("SanMiguelSun", vaVector3(1.25f, 1.18f, 1.05f),
            vaVector3(-0.35f, 0.45f, -1.0f).Normalized())));

    VA_LOG(L"Loaded San Miguel external cache '%s': materials=%u, textures=%u, chunks=%u, vertices=%llu, triangles=%llu",
        cachePath.c_str(), materialCount, (uint32)m_sanMiguelPreviewTextures.size(),
        chunkCount, (unsigned long long)loadedVertexCount,
        (unsigned long long)(loadedIndexCount / 3));
    return true;
}

// for conversion to mpeg one option is to download ffmpeg and then do 'ffmpeg -r 60 -f image2 -s 1920x1080 -i SuperSampleReference_frame_%05d.png -vcodec libx264 -crf 13  -pix_fmt yuv420p outputvideo.mp4'
class BenchItemRecordSSReference : public AutoBenchToolWorkItem
{
    const float     c_frameDeltaTime = 1.0f / 60.0f;
    const int       c_totalFrameCount;
    int             m_currentAAOption;
    bool            m_isDone;
    int             m_currentFrame;
public:
    BenchItemRecordSSReference(CMAA2Sample& parent) : AutoBenchToolWorkItem(parent), m_currentFrame(-1), m_currentAAOption(-1), c_totalFrameCount((int)(parent.GetFlythroughCameraController()->GetTotalTime() / c_frameDeltaTime)), m_isDone(false) {}

protected:
    virtual void    Tick(AutoBenchTool& abTool, float deltaTime) override
    {
        deltaTime;
        abTool;

        // Init on start
        if (m_currentAAOption == -1)
        {
            m_parent.Settings().CurrentAAOption = CMAA2Sample::AAType::SuperSampleReference;
            m_currentAAOption++;
            m_currentFrame = -5;   // loop few frames 'on empty' to flush out any interference, driver heuristic, whatnots
            abTool.ReportStart();
        }

        m_currentFrame++;

        // finished
        if (m_currentFrame >= c_totalFrameCount)
        {
            m_isDone = true;
            abTool.ReportFinish();
        }
        else
        {
        }

        m_parent.GetFlythroughCameraController()->SetPlayTime(vaMath::Max(0.0f, m_currentFrame * c_frameDeltaTime));
    }
    virtual void    OnRender(AutoBenchTool&) override {}
    virtual void    OnRenderComparePoint(AutoBenchTool& abTool, vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext, const shared_ptr<vaTexture>& colorInOut, shared_ptr<vaPostProcess>& postProcess) override
    {
        abTool; imageCompareTool; postProcess;
        if (m_currentFrame >= 0 && m_currentFrame < c_totalFrameCount)
        {
            colorInOut->SaveToPNGFile(renderContext, abTool.ReportGetDir() + vaStringTools::SimpleWiden(vaStringTools::Format("%s_frame_%05d.png", m_parent.GetAAName(m_parent.Settings().CurrentAAOption), m_currentFrame)));
        }
    }
    virtual bool    IsDone(AutoBenchTool&) const override { return m_isDone; }
    virtual float   GetProgress() const override { return (float)m_currentFrame / (c_totalFrameCount - 1); }
};

void AutoBenchTool::Tick(float deltaTime)
{
    if (m_currentTask == nullptr)
    {
        if (m_tasks.size() > 0)
        {
            m_currentTask = m_tasks.back();
            m_tasks.pop_back();
            m_backupSettings = m_parent.Settings();
            m_backupSMAAPreset = m_parent.GetSMAAPreset();
            m_backupCamera = *m_parent.Camera();
            m_backupTonemapSettings = m_parent.PostProcessTonemap()->Settings();
            m_backupFlythroughCameraTime = m_parent.GetFlythroughCameraController()->GetPlayTime();
            m_backupFlythroughCameraSpeed = m_parent.GetFlythroughCameraController()->GetPlaySpeed();
            m_backupFlythroughCameraEnabled = m_parent.GetFlythroughCameraEnabled();

            string info = "System info:  " + vaCore::GetCPUIDName() + ", " + m_parent.GetRenderDevice().GetAdapterNameShort();
            info += "\r\nAPI:  " + m_parent.GetRenderDevice().GetAPIName();
            if ((m_parent.GetRenderDevice().GetAPIName() == "DirectX12"))
                info += " (not yet fully optimized implementation)";
            ReportAddText(info + "\r\n\r\n");

            ReportAddText(vaStringTools::Format("Resolution:   %d x %d\r\n", m_parent.GetApplication().GetWindowClientAreaSize().x, m_parent.GetApplication().GetWindowClientAreaSize().y));
            ReportAddText(vaStringTools::Format("Vsync:        ") + ((m_parent.GetApplication().GetSettings().Vsync) ? ("!!ON!!") : ("OFF")) + "\r\n");

            string fullscreenState;
            switch (m_parent.GetApplication().GetFullscreenState())
            {
            case (vaFullscreenState::Windowed):               fullscreenState = "Windowed"; break;
            case (vaFullscreenState::Fullscreen):             fullscreenState = "Fullscreen"; break;
            case (vaFullscreenState::FullscreenBorderless):   fullscreenState = "Fullscreen Borderless"; break;
            case (vaFullscreenState::Unknown):
            default: fullscreenState = "Unknown";
                break;
            }

            ReportAddText("Fullscreen:   " + fullscreenState + "\r\n");
            ReportAddText("\r\n");

            // flythrough used
            m_parent.SetFlythroughCameraEnabled(true);
            m_parent.GetFlythroughCameraController()->SetPlaySpeed(0.0f);
            m_parent.GetFlythroughCameraController()->SetPlayTime(0.0f);
        }
    }

    if (m_currentTask != nullptr)
    {
        m_currentTask->Tick(*this, deltaTime);

        if (m_currentTask->IsDone(*this))
        {
            m_parent.Settings() = m_backupSettings;
            m_parent.SetSMAAPreset(m_backupSMAAPreset);
            *m_parent.Camera() = m_backupCamera;
            m_parent.PostProcessTonemap()->Settings() = m_backupTonemapSettings;
            m_parent.GetFlythroughCameraController()->SetPlayTime(m_backupFlythroughCameraTime);
            m_parent.GetFlythroughCameraController()->SetPlaySpeed(m_backupFlythroughCameraSpeed);
            m_parent.SetFlythroughCameraEnabled(m_backupFlythroughCameraEnabled);
            m_parent.SetRequireDeterminism(false);
            m_parent.SetFixedDeltaTime(0.0f);
            m_currentTask = nullptr;
        }
    }
}

void AutoBenchTool::OnRender()
{
    if (m_currentTask != nullptr)
        m_currentTask->OnRender(*this);
}
void AutoBenchTool::OnRenderComparePoint(vaImageCompareTool& imageCompareTool, vaRenderDeviceContext& renderContext, const shared_ptr<vaTexture>& colorInOut, shared_ptr<vaPostProcess>& postProcess)
{
    if (m_currentTask != nullptr)
        m_currentTask->OnRenderComparePoint(*this, imageCompareTool, renderContext, colorInOut, postProcess);
}

void    AutoBenchTool::ReportStart()
{
    assert(m_reportDir == L"");
    assert(m_reportCSV.size() == 0);

    m_reportDir = vaCore::GetExecutableDirectory();

    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);

    std::wstringstream ss;
#pragma warning ( suppress : 4996 )
    ss << std::put_time(std::localtime(&in_time_t), L"%Y%m%d_%H%M%S");
    m_reportDir += L"AutoBench\\" + ss.str() + L"\\";

    m_reportName = ss.str();

    vaFileTools::DeleteDirectory(m_reportDir);
    vaFileTools::EnsureDirectoryExists(m_reportDir);
}

void    AutoBenchTool::FlushRowValues()
{
    for (int i = 0; i < m_reportCSV.size(); i++)
    {
        vector<string> row = m_reportCSV[i];
        string rowText;
        for (int j = 0; j < row.size(); j++)
        {
            rowText += row[j] + ", ";
        }
        m_reportTXT += rowText + "\r\n";
    }
    m_reportCSV.clear();
}

void    AutoBenchTool::ReportFinish()
{
    if (m_reportDir != L"")
    {
        // {
        //     vaFileStream outFile;
        //     outFile.Open( m_reportDir + m_reportName + L"_info.txt", (false)?(FileCreationMode::Append):(FileCreationMode::Create) );
        //     outFile.WriteTXT( m_reportTXT );
        // }

        FlushRowValues();

        {
            vaFileStream outFile;
            outFile.Open(m_reportDir + m_reportName + L"_results.csv", (false) ? (FileCreationMode::Append) : (FileCreationMode::Create));
            outFile.WriteTXT(m_reportTXT);
            outFile.WriteTXT("\r\n");
        }

        VA_LOG(L"Report written to '%s'", m_reportDir.c_str());
    }
    else
    {
        assert(false);
    }
    m_reportCSV.clear();
    m_reportTXT = "";
    m_reportDir = L"";
}


void CMAA2Sample::UIPanelDraw()
{
    //ImGui::Checkbox( "Texturing disabled", &m_debugTexturingDisabled );

#ifdef VA_IMGUI_INTEGRATION_ENABLED
    if (m_autoBench->IsActive())
    {
        ImGui::Text("AUTOBENCH ACTIVE");
        ImGui::Text("Current task %3.1f%% done, %d remaining)", m_autoBench->GetProgress() * 100.0f, m_autoBench->GetQueuedTaskCount());
        return;
    }

    if (m_currentDrawResults != vaDrawResultFlags::None)
    {
        ImGui::Text("SCENE DRAW INCOMPLETE");
        ImGui::Text("");
        ImGui::Text("Asset/shader still loading or compiling");
        return;
    }

    //#define SAMPLE_BUILD_FOR_LAB
#ifndef SAMPLE_BUILD_FOR_LAB
    int sceneSettingsIndex = vaMath::Clamp((int)m_settings.SceneChoice, 0, (int)SceneSelectionType::MaxValue - 1);

    vector<string> sceneNames;
    for (const shared_ptr<vaScene>& scene : m_scenes)
        sceneNames.push_back(scene->Name());

    if (ImGuiEx_Combo("Scene", sceneSettingsIndex, sceneNames))
    {
        //imguiStateStorage->SetInt( displayTypeID, displayTypeIndex );
    }
    m_settings.SceneChoice = (SceneSelectionType)(sceneSettingsIndex);

    bool aaTypeApplicable[(int)AAType::MaxValue]; for (int i = 0; i < _countof(aaTypeApplicable); i++) aaTypeApplicable[i] = true;
    if (m_settings.SceneChoice == CMAA2Sample::SceneSelectionType::StaticImage)
    {
        ImGui::Indent();
        if (m_staticImageList.size() > 0)
        {
            ImGuiEx_Combo("Image", m_settings.CurrentStaticImageChoice, m_staticImageList);
        }
        else
        {
            ImGui::Text("No images");
        }

        if (ImGui::Button("Open screenshot folder"))
            vaFileTools::OpenSystemExplorerFolder(m_screenshotFolder);

        ImGui::Unindent();

        // these don't work on screenshots
        aaTypeApplicable[(int)AAType::MSAA2x] = false;
        aaTypeApplicable[(int)AAType::MSAA4x] = false;
        aaTypeApplicable[(int)AAType::MSAA8x] = false;
#if MSAA_16x_SUPPORTED
        aaTypeApplicable[(int)AAType::MSAA16x] = false;
#endif
        aaTypeApplicable[(int)AAType::MSAA2xPlusCMAA2] = false;
        aaTypeApplicable[(int)AAType::MSAA4xPlusCMAA2] = false;
        aaTypeApplicable[(int)AAType::MSAA8xPlusCMAA2] = false;
        aaTypeApplicable[(int)AAType::SuperSampleReference] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA] = true;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_O_T2X] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_O_T2X_R] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_O_ET2X] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_O_ET2X_R] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_A_T2X] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_A_T2X_R] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_A_ET2X] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_A_ET2X_R] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::SMAA_S2x] = false;
        aaTypeApplicable[(int)CMAA2Sample::AAType::FXAA] = true;
        //                        aaTypeApplicable[(int)AAType::ExperimentalSlot1]    = false;
        //                        aaTypeApplicable[(int)AAType::ExperimentalSlot2]    = false;
    }
    else if (m_settings.SceneChoice == CMAA2Sample::SceneSelectionType::LumberyardBistro)
    {
        ImGui::Indent();
        ImGui::Checkbox("Play animation", &m_flythroughPlay);
        ImGui::Checkbox("Show wireframe", &m_settings.ShowWireframe);
        if (ImGui::IsItemHovered()) ImGui::SetTooltip("Wireframe");
        ImGui::Unindent();
    }
    else
    {
        ImGui::Indent();
        ImGui::Checkbox("Show wireframe", &m_settings.ShowWireframe);
        ImGui::Unindent();
    }
    ImGui::Separator();

    const char* vals[(int)AAType::MaxValue];
    for (int i = 0; i < _countof(aaTypeApplicable); i++)
        vals[i] = GetAAName((AAType)i);

    for (int i = 0; i < _countof(aaTypeApplicable); i++)
        if (!aaTypeApplicable[i]) vals[i] = "(not applicable for screenshots)";

    AAType prevAAOption = m_settings.CurrentAAOption;
    ImGui::ListBox("AA option", (int*)&m_settings.CurrentAAOption, vals, (int)AAType::MaxValue, (int)AAType::MaxValue);

    // some modes not applicable for static images (screenshots)
    if (!aaTypeApplicable[(int)m_settings.CurrentAAOption])
        m_settings.CurrentAAOption = prevAAOption;

    int msaaSampleCount = GetMSAACountForAAType(m_settings.CurrentAAOption);

    if (msaaSampleCount > 1)
    {
        ImGui::Indent();

        int dbgOption = m_settings.MSAADebugSampleIndex + 1;
        if (msaaSampleCount == 2)
            ImGuiEx_Combo("MSAA debug", dbgOption, vector<string>({ "No MSAA debugging", "MSAA show only slice 0", "MSAA show only slice 1" }));
        else if (msaaSampleCount == 4)
            ImGuiEx_Combo("MSAA debug", dbgOption, vector<string>({ "No MSAA debugging", "MSAA show only slice 0", "MSAA show only slice 1", "MSAA show only slice 2", "MSAA show only slice 3" }));
        else if (msaaSampleCount == 8)
            ImGuiEx_Combo("MSAA debug", dbgOption, vector<string>({ "No MSAA debugging", "MSAA show only slice 0", "MSAA show only slice 1", "MSAA show only slice 2", "MSAA show only slice 3", "MSAA show only slice 4", "MSAA show only slice 5", "MSAA show only slice 6", "MSAA show only slice 7" }));
        else if (msaaSampleCount == 16)
            ImGuiEx_Combo("MSAA debug", dbgOption, vector<string>({ "No MSAA debugging", "MSAA show only slice 0", "MSAA show only slice 1", "MSAA show only slice 2", "MSAA show only slice 3", "MSAA show only slice 4", "MSAA show only slice 5", "MSAA show only slice 6", "MSAA show only slice 7", "MSAA show only slice 8", "MSAA show only slice 9", "MSAA show only slice 10", "MSAA show only slice 11", "MSAA show only slice 12", "MSAA show only slice 13", "MSAA show only slice 14", "MSAA show only slice 15" }));
        else { assert(false); }

        ImGui::Unindent();
        m_settings.MSAADebugSampleIndex = dbgOption - 1;
    }

    if (m_settings.CurrentAAOption == CMAA2Sample::AAType::CMAA2 || m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA2xPlusCMAA2 || m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA4xPlusCMAA2 || m_settings.CurrentAAOption == CMAA2Sample::AAType::MSAA8xPlusCMAA2)
        m_CMAA2->UIPanelDrawCollapsable(false, true, true);

    if (IsSMAASingleSample(m_settings.CurrentAAOption) || m_settings.CurrentAAOption == CMAA2Sample::AAType::SMAA_S2x)
        m_SMAA->UIPanelDrawCollapsable(false, true, true);

    if (m_settings.CurrentAAOption == CMAA2Sample::AAType::FXAA)
        m_FXAA->UIPanelDrawCollapsable(false, true, true);

#if 0 // reducing UI clutter
    if (m_settings.CurrentAAOption == CMAA2Sample::AAType::SuperSampleReference)
    {
        ImGui::Text("SuperSampleReference works on 2 levels:");
        ImGui::Text("scene is rendered at 2x height & width, ");
        ImGui::Text("with box downsample; also, each pixel");
        ImGui::Text("is average of PixGridRes x PixGridRes");
        ImGui::Text("samples (so total sample count per pixel");
        ImGui::Text("is (2*2*PixGridRes*PixGridRes).");
        ImGui::InputInt("SS PixGridRes", &m_SSGridRes);
        m_SSGridRes = vaMath::Clamp(m_SSGridRes, 1, 8);
        ImGui::InputFloat("SS textures MIP bias", &m_SSMIPBias, 0.05f);
        m_SSMIPBias = vaMath::Clamp(m_SSMIPBias, -10.0f, 10.0f);
        ImGui::InputFloat("SS sharpen", &m_SSSharpen, 0.01f);
        m_SSSharpen = vaMath::Clamp(m_SSSharpen, 0.0f, 1.0f);
        ImGui::InputFloat("SS ddx/ddy bias", &m_SSDDXDDYBias, 0.05f);
        m_SSDDXDDYBias = vaMath::Clamp(m_SSDDXDDYBias, 0.0f, 1.0f);
    }
#endif

    if (m_settings.SceneChoice != CMAA2Sample::SceneSelectionType::StaticImage)
    {
        ImGui::Separator();
        ImGui::Indent();

#if 0 // reducing UI clutter
        float yfov = m_settings.CameraYFov / (VA_PIf) * 180.0f;
        ImGui::InputFloat("Camera Y FOV", &yfov, 5.0f, 0.0f, 1);
        m_settings.CameraYFov = vaMath::Clamp(yfov, 20.0f, 140.0f) * (VA_PIf) / 180.0f;
        if (ImGui::IsItemHovered()) ImGui::SetTooltip("Camera Y field of view");

        ImGui::Checkbox("Z-Prepass", &m_settings.ZPrePass);
#endif
        ImGui::Unindent();
    }

#endif

    // Benchmarking
    // if (m_settings.SceneChoice != CMAA2Sample::SceneSelectionType::StaticImage)
    // static 이미지도 밴치마킹
    if (true)
    {
        if (ImGui::IsKeyPressed((int)vaKeyboardKeys::KK_F8, false) && !m_autoBench->IsActive())
            m_queueEightCasePerformanceBenchmark = true;

        ImGuiTreeNodeFlags headerFlags = 0;
        // headerFlags |= ImGuiTreeNodeFlags_Framed;
        headerFlags |= ImGuiTreeNodeFlags_DefaultOpen;

        assert(!m_autoBench->IsActive());

        bool isDebug = false;
#ifdef _DEBUG
        isDebug = true;
#endif

        if (m_queueEightCasePerformanceBenchmark)
        {
            m_queueEightCasePerformanceBenchmark = false;
            m_SMAA->SetTemporalCandidateStatisticsReadbackEnabled(false);
            m_autoBench->AddTask(std::make_shared<BenchItemSMAATemporalPerformanceBenchmark>(
                *this, 1.0f, 300, 4800, 3, true));
        }

        if (ImGui::CollapsingHeader("Benchmarking", headerFlags))
        {
            if (m_settings.SceneChoice == CMAA2Sample::SceneSelectionType::StaticImage)
            {
                // static 이미지도 지원
                ImGui::Text("Notice: Benchmarking on Static Image (Pure AA Perf)");
                // ImGui::Text("Benchmarking doesn't work in screenshot mode");
                // ImGui::Text("(please select a scene)");
            }
            if (isDebug)
            {
                ImGui::Text("Benchmarking doesn't work in debug builds");
            }
            else
            {
                ImGui::Indent();

#ifndef SAMPLE_BUILD_FOR_LAB
                if (ImGui::Button("Run visual quality benchmarks"))
                {
                    m_autoBench->AddTask(std::make_shared<BenchItemCompareAllToRef>(*this));
                }
                ImGui::Separator();

                ImGui::Text("SMAA temporal quality capture (60 FPS flythrough)");
                ImGui::InputFloat("Capture start time (s)", &m_temporalComparisonStartTime, 0.5f, 1.0f, "%.2f");
                ImGui::InputInt("Capture frames per mode", &m_temporalComparisonFrameCount);
                ImGui::InputInt("Temporal warm-up frames", &m_temporalComparisonWarmupFrames);
                m_temporalComparisonStartTime = vaMath::Max(0.0f, m_temporalComparisonStartTime);
                m_temporalComparisonFrameCount = vaMath::Clamp(m_temporalComparisonFrameCount, 1, 1800);
                m_temporalComparisonWarmupFrames = vaMath::Clamp(m_temporalComparisonWarmupFrames, 0, 600);

                const vaVector2i temporalCaptureResolution = m_application.GetWindowClientAreaSize();
                if (temporalCaptureResolution != vaVector2i(1920, 1080))
                    ImGui::TextColored(ImVec4(1.0f, 0.65f, 0.0f, 1.0f), "Formal capture requires 1920 x 1080 (current: %d x %d)", temporalCaptureResolution.x, temporalCaptureResolution.y);
                if (m_application.GetSettings().Vsync)
                    ImGui::TextColored(ImVec4(1.0f, 0.25f, 0.25f, 1.0f), "Disable VSync before formal capture");
                ImGui::TextDisabled("300 frames per mode uses approximately 1.5 GB at 1080p");

                if (ImGui::Button("Capture SMAA 1X vs O-T2X vs O-T2X-R"))
                {
                    m_autoBench->AddTask(std::make_shared<BenchItemRecordSMAATemporalComparison>(*this,
                        m_temporalComparisonStartTime, m_temporalComparisonFrameCount, m_temporalComparisonWarmupFrames));
                }
                ImGui::SameLine();
                ImGui::TextDisabled("PNG sequences are saved under AutoBench");

                if (ImGui::Button("Capture Original SMAA four temporal modes"))
                {
                    m_autoBench->AddTask(std::make_shared<BenchItemRecordSMAATemporalMatrix>(*this,
                        m_temporalComparisonStartTime, m_temporalComparisonFrameCount, m_temporalComparisonWarmupFrames, false));
                }
                ImGui::SameLine();
                ImGui::TextDisabled("Separate deterministic pair capture");

                if (ImGui::Button("Capture full SMAA eight-case matrix"))
                {
                    m_autoBench->AddTask(std::make_shared<BenchItemRecordSMAATemporalMatrix>(*this,
                        m_temporalComparisonStartTime, m_temporalComparisonFrameCount, m_temporalComparisonWarmupFrames, true));
                }
                ImGui::SameLine();
                ImGui::TextDisabled("Original + Adaptive, 8 PNG sequences");
                ImGui::Separator();

                if (ImGui::Button("Run SMAA eight-case performance benchmark"))
                {
                    m_queueEightCasePerformanceBenchmark = true;
                }
                ImGui::SameLine();
                ImGui::TextDisabled("F8 | 8 modes, 3 repeats, 300 warm-up + 4800 measured frames");
                ImGui::Separator();
#endif
                const char* dx11 = "Run performance benchmarks (DX11)";
                const char* dx12 = "Run performance benchmarks (DX12, not fully optimized)";

                if (ImGui::Button((GetRenderDevice().GetAPIName() == "DirectX11") ? (dx11) : (dx12)))
                {
                    for (int i = 0; i < m_autoBenchPerfRunCount; i++)
                        m_autoBench->AddTask(std::make_shared<BenchItemPerformance>(*this));
                }
                ImGui::InputInt("Loop count", &m_autoBenchPerfRunCount);
                m_autoBenchPerfRunCount = vaMath::Clamp(m_autoBenchPerfRunCount, 1, 10);

                ImGui::Unindent();
            }
            ImGui::Separator();
            if (ImGui::Button("Run SMAA-only GPU time benchmark"))
            {
                m_autoBench->AddTask(std::make_shared<BenchItemSMAAOnly>(*this));
            }
            ImGui::SameLine();
            ImGui::TextDisabled("(measures SMAA pass GPU ms only)");
        }
    }

#endif
}

// #include "Rendering/DirectX/vaRenderDeviceContextDX11.h"
// #include "Rendering/DirectX/vaRenderingToolsDX11.h"

namespace VertexAsylum
{
    // totally unneeded at the moment - there's no API-specific stuff (but leaving it in for future need)
    class CMAA2SampleDX11 : public CMAA2Sample
    {
        VA_RENDERING_MODULE_MAKE_FRIENDS();
    private:
        explicit CMAA2SampleDX11(const vaRenderingModuleParams& params) : CMAA2Sample(params) {}
        ~CMAA2SampleDX11() {}
    };
    class CMAA2SampleDX12 : public CMAA2Sample
    {
        VA_RENDERING_MODULE_MAKE_FRIENDS();
    private:
        explicit CMAA2SampleDX12(const vaRenderingModuleParams& params) : CMAA2Sample(params) {}
        ~CMAA2SampleDX12() {}
    };
}

void RegisterCMAA2SampleDX11()
{
    VA_RENDERING_MODULE_REGISTER(vaRenderDeviceDX11, CMAA2Sample, CMAA2SampleDX11);
}
void RegisterCMAA2SampleDX12()
{
    VA_RENDERING_MODULE_REGISTER(vaRenderDeviceDX12, CMAA2Sample, CMAA2SampleDX12);
}

void InitializeProjectAPIParts()
{
    //useDX12;
    //if( !useDX12 )
    {
        void RegisterCMAA2SampleDX11();
        void RegisterSMAAWrapperDX11();
        void RegisterCMAA2DX11();
        RegisterCMAA2SampleDX11();
        RegisterCMAA2DX11();
        RegisterSMAAWrapperDX11();
    }
    //    else
    {
        void RegisterCMAA2SampleDX12();
        void RegisterSMAAWrapperDX12();
        void RegisterCMAA2DX12();
        RegisterCMAA2SampleDX12();
        RegisterSMAAWrapperDX12();
        RegisterCMAA2DX12();
    }
}

