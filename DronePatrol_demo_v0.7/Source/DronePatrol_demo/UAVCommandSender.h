// UAVCommandSender.h
// UE 4.27 端 UDP 指令发送器 —— 将蓝图层触发的指令通过 Socket 发送到 Python 控制层

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UAVCommandSender.generated.h"

// 指令结构体（蓝图可用）
USTRUCT(BlueprintType)
struct FUAVCommand
{
    GENERATED_BODY()

    // 指令类型: "takeoff", "land", "hover", "returnHome", "moveTo", "formation", "allTakeoff", "allLand"
    UPROPERTY(BlueprintReadWrite, Category = "UAV Command")
    FString CommandType;

    // 目标无人机 ID（1~4），0 表示所有无人机
    UPROPERTY(BlueprintReadWrite, Category = "UAV Command")
    int32 TargetUAVId = 1;

    // 目标位置（moveTo 时使用）
    UPROPERTY(BlueprintReadWrite, Category = "UAV Command")
    FVector TargetLocation = FVector::ZeroVector;

    // 编队类型（formation 时使用）: "V", "line", "column", "diamond"
    UPROPERTY(BlueprintReadWrite, Category = "UAV Command")
    FString FormationType;

    // 编队中心点
    UPROPERTY(BlueprintReadWrite, Category = "UAV Command")
    FVector FormationCenter = FVector::ZeroVector;
};

UCLASS(Blueprintable)
class DRONEPATROL_DEMO_API AUAVCommandSender : public AActor
{
    GENERATED_BODY()

public:
    AUAVCommandSender();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
    // ---- 蓝图可调用接口 ----

    // 发送单条指令
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendCommand(const FUAVCommand& Command);

    // 快捷方法：让单架无人机起飞
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendTakeoff(int32 UAVId);

    // 快捷方法：让单架无人机降落
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendLand(int32 UAVId);

    // 快捷方法：让所有无人机起飞
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendAllTakeoff();

    // 快捷方法：让所有无人机降落
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendAllLand();

    // 快捷方法：单机悬停
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendHover(int32 UAVId);

    // 快捷方法：单机返航
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendReturnHome(int32 UAVId);

    // 快捷方法：单机移动到目标点
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendMoveTo(int32 UAVId, FVector TargetLocation, float Speed = 5.0f);

    // 快捷方法：编队飞行
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendFormation(const FString& FormationType, FVector Center, float Speed = 5.0f);

    // 快捷方法：全部悬停
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendAllHover();

    // 快捷方法：启动编队保持（Leader-Follower）
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendFormationHold(const FString& FormationType, FVector Center, float Speed = 5.0f);

    // 快捷方法：启动协同巡逻
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendPatrol(const FString& FormationType, float Speed = 5.0f);

    // 快捷方法：停止协同控制
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    void SendStopCoop();

    // 获取最后一次发送状态
    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    bool GetLastSendStatus() const { return bLastSendSuccess; }

    UFUNCTION(BlueprintCallable, Category = "UAV Command")
    FString GetLastErrorMessage() const { return LastErrorMessage; }

private:
    // 控制面板曾把 PlayerController 设为 UIOnly，导致 AirSim 的相机输入
    // （M、方向键等）完全收不到。BeginPlay 的下一帧恢复为 GameAndUI。
    void ConfigureInputForCameraControl();

    // 底层 UDP 发送
    void SendUDPMessage(const FString& JSONMessage);

    // 构建 JSON 字符串
    FString BuildCommandJSON(const FString& Type, int32 UAVId, FVector Location,
                             float Speed, const FString& Formation, FVector Center) const;

    // ---- UDP Socket ----
    class FSocket* UDPSocket;

    // Python 监听地址
    FString RemoteAddress;
    int32 RemotePort;

    // 发送状态追踪
    bool bLastSendSuccess;
    FString LastErrorMessage;
};
