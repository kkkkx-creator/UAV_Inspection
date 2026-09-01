// UAVCommandSender.cpp
// UE 4.27 端 UDP 指令发送器实现

#include "UAVCommandSender.h"
#include "Common/UdpSocketBuilder.h"
#include "SocketSubsystem.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "Interfaces/IPv4/IPv4Endpoint.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Dom/JsonObject.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/PlayerController.h"

AUAVCommandSender::AUAVCommandSender()
{
    PrimaryActorTick.bCanEverTick = false;

    UDPSocket = nullptr;
    RemoteAddress = TEXT("127.0.0.1");
    RemotePort = 9876;
    bLastSendSuccess = true;
    LastErrorMessage = TEXT("");
}

void AUAVCommandSender::BeginPlay()
{
    Super::BeginPlay();

    // 创建 UDP Socket
    // 在 UE4 中使用 FUdpSocketBuilder
    FIPv4Address IP;
    FIPv4Address::Parse(RemoteAddress, IP);

    FIPv4Endpoint Endpoint(IP, RemotePort);

    // 注意：UE4.27 的 FUdpSocketBuilder 签名
    // FUdpSocketBuilder(const FString& SocketName)
    UDPSocket = FUdpSocketBuilder(TEXT("UAVCommandSocket"))
        .AsNonBlocking()        // 非阻塞模式，不卡住游戏线程
        .WithBroadcast()        // 允许广播
        .WithSendBufferSize(65536)
        .BoundToPort(0)         // 端口 0 = 系统自动分配本机端口
        .Build();

    if (UDPSocket)
    {
        UE_LOG(LogTemp, Log, TEXT("UAVCommandSender: UDP Socket created successfully. Sending to %s:%d"),
               *RemoteAddress, RemotePort);
        bLastSendSuccess = true;
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("UAVCommandSender: Failed to create UDP Socket!"));
        bLastSendSuccess = false;
        LastErrorMessage = TEXT("Socket creation failed");
    }

    // 在关卡蓝图创建控制面板之后执行，以覆盖其中的 Set Input Mode UIOnly。
    // GameAndUI 保留鼠标点击 UMG 的能力，同时把未被控件消费的按键交给
    // AirSim 的 CameraDirector（Manual 视角）。
    GetWorldTimerManager().SetTimerForNextTick(this, &AUAVCommandSender::ConfigureInputForCameraControl);
}

void AUAVCommandSender::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    // 关闭并销毁 Socket
    if (UDPSocket)
    {
        UDPSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(UDPSocket);
        UDPSocket = nullptr;
        UE_LOG(LogTemp, Log, TEXT("UAVCommandSender: UDP Socket closed."));
    }

    Super::EndPlay(EndPlayReason);
}

void AUAVCommandSender::ConfigureInputForCameraControl()
{
    APlayerController* PlayerController = UGameplayStatics::GetPlayerController(this, 0);
    if (!PlayerController)
    {
        UE_LOG(LogTemp, Warning, TEXT("UAVCommandSender: PlayerController unavailable; camera input was not configured."));
        return;
    }

    FInputModeGameAndUI InputMode;
    InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    PlayerController->SetInputMode(InputMode);
    PlayerController->bShowMouseCursor = true;
    UE_LOG(LogTemp, Log, TEXT("UAVCommandSender: Input mode set to GameAndUI for AirSim camera control."));
}

// ---- 蓝图接口实现 ----

void AUAVCommandSender::SendCommand(const FUAVCommand& Command)
{
    FString JSON = BuildCommandJSON(
        Command.CommandType,
        Command.TargetUAVId,
        Command.TargetLocation,
        5.0f,                           // 默认速度
        Command.FormationType,
        Command.FormationCenter
    );
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendTakeoff(int32 UAVId)
{
    FString JSON = BuildCommandJSON(TEXT("takeoff"), UAVId, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendLand(int32 UAVId)
{
    FString JSON = BuildCommandJSON(TEXT("land"), UAVId, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendAllTakeoff()
{
    FString JSON = BuildCommandJSON(TEXT("allTakeoff"), 0, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendAllLand()
{
    FString JSON = BuildCommandJSON(TEXT("allLand"), 0, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendHover(int32 UAVId)
{
    FString JSON = BuildCommandJSON(TEXT("hover"), UAVId, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendReturnHome(int32 UAVId)
{
    FString JSON = BuildCommandJSON(TEXT("returnHome"), UAVId, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendMoveTo(int32 UAVId, FVector TargetLocation, float Speed)
{
    FString JSON = BuildCommandJSON(TEXT("moveTo"), UAVId, TargetLocation, Speed, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendFormation(const FString& FormationType, FVector Center, float Speed)
{
    FString JSON = BuildCommandJSON(TEXT("formation"), 0, FVector::ZeroVector, Speed, FormationType, Center);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendAllHover()
{
    FString JSON = BuildCommandJSON(TEXT("allHover"), 0, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendFormationHold(const FString& FormationType, FVector Center, float Speed)
{
    FString JSON = BuildCommandJSON(TEXT("formationHold"), 0, FVector::ZeroVector, Speed, FormationType, Center);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendPatrol(const FString& FormationType, float Speed)
{
    FString JSON = BuildCommandJSON(TEXT("patrol"), 0, FVector::ZeroVector, Speed, FormationType, FVector::ZeroVector);
    SendUDPMessage(JSON);
}

void AUAVCommandSender::SendStopCoop()
{
    FString JSON = BuildCommandJSON(TEXT("stopCoop"), 0, FVector::ZeroVector, 0, TEXT(""), FVector::ZeroVector);
    SendUDPMessage(JSON);
}

// ---- JSON 构建 ----

FString AUAVCommandSender::BuildCommandJSON(const FString& Type, int32 UAVId, FVector Location,
                                             float Speed, const FString& Formation, FVector Center) const
{
    // 使用 UE4 内置 JSON 库构建
    TSharedPtr<FJsonObject> JsonObj = MakeShareable(new FJsonObject);

    JsonObj->SetStringField(TEXT("type"), Type);
    JsonObj->SetNumberField(TEXT("uav_id"), UAVId);
    JsonObj->SetNumberField(TEXT("speed"), Speed);

    // 位置信息
    TSharedPtr<FJsonObject> PosObj = MakeShareable(new FJsonObject);
    PosObj->SetNumberField(TEXT("x"), Location.X);
    PosObj->SetNumberField(TEXT("y"), Location.Y);
    PosObj->SetNumberField(TEXT("z"), Location.Z);
    JsonObj->SetObjectField(TEXT("target"), PosObj);

    // 编队信息（如果有）
    if (!Formation.IsEmpty())
    {
        JsonObj->SetStringField(TEXT("formation_type"), Formation);

        TSharedPtr<FJsonObject> CenterObj = MakeShareable(new FJsonObject);
        CenterObj->SetNumberField(TEXT("x"), Center.X);
        CenterObj->SetNumberField(TEXT("y"), Center.Y);
        CenterObj->SetNumberField(TEXT("z"), Center.Z);
        JsonObj->SetObjectField(TEXT("formation_center"), CenterObj);
    }

    // 序列化为 JSON 字符串
    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

    return OutputString;
}

// ---- 底层 UDP 发送 ----

void AUAVCommandSender::SendUDPMessage(const FString& JSONMessage)
{
    if (!UDPSocket)
    {
        bLastSendSuccess = false;
        LastErrorMessage = TEXT("Socket is null");
        UE_LOG(LogTemp, Error, TEXT("UAVCommandSender: Cannot send - socket is null"));
        return;
    }

    // 解析目标地址
    FIPv4Address IP;
    if (!FIPv4Address::Parse(RemoteAddress, IP))
    {
        bLastSendSuccess = false;
        LastErrorMessage = FString::Printf(TEXT("Invalid IP address: %s"), *RemoteAddress);
        UE_LOG(LogTemp, Error, TEXT("UAVCommandSender: %s"), *LastErrorMessage);
        return;
    }

    FIPv4Endpoint Endpoint(IP, RemotePort);

    // 将 FString 转为字节数组
    FTCHARToUTF8 Converter(*JSONMessage);
    TArray<uint8> Data;
    Data.Append((uint8*)Converter.Get(), Converter.Length());

    int32 BytesSent = 0;
    bool bSuccess = UDPSocket->SendTo(Data.GetData(), Data.Num(), BytesSent, *Endpoint.ToInternetAddr());

    if (bSuccess && BytesSent > 0)
    {
        bLastSendSuccess = true;
        LastErrorMessage = TEXT("");
        UE_LOG(LogTemp, Log, TEXT("UAVCommandSender: Sent %d bytes → %s:%d | %s"),
               BytesSent, *RemoteAddress, RemotePort, *JSONMessage);
    }
    else
    {
        bLastSendSuccess = false;
        LastErrorMessage = FString::Printf(TEXT("SendTo failed. BytesSent=%d"), BytesSent);
        UE_LOG(LogTemp, Warning, TEXT("UAVCommandSender: %s"), *LastErrorMessage);
    }
}
