// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UAVMonitor.generated.h"

// 无人机状态结构体（蓝图可用）
USTRUCT(BlueprintType)
struct FUAVState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly)
    int32 UAVId = 0;

    UPROPERTY(BlueprintReadOnly)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(BlueprintReadOnly)
    float BatteryPercent = 100.0f;

    UPROPERTY(BlueprintReadOnly)
    float SpeedKmh = 0.0f;

    UPROPERTY(BlueprintReadOnly)
    FString TaskStatus = TEXT("Idle");

    UPROPERTY(BlueprintReadOnly)
    FString TaskType = TEXT("None");

    UPROPERTY(BlueprintReadOnly)
    float TaskProgress = 0.0f;

    UPROPERTY(BlueprintReadOnly)
    bool bHasFault = false;

    UPROPERTY(BlueprintReadOnly)
    FString FaultType = TEXT("");
};

// 状态更新委托（注意大小写：FOnUAVStateUpdated）
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnUAVStateUpdated, const FUAVState&, NewState);

UCLASS()
class DRONEPATROL_DEMO_API AUAVMonitor : public AActor
{
    GENERATED_BODY()

public:
    AUAVMonitor();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaTime) override;   // 改用Tick，简单可靠

public:
    // UI绑定的委托
    UPROPERTY(BlueprintAssignable, Category = "UAVMonitor")
    FOnUAVStateUpdated OnUAVStateUpdated;

    // 获取所有状态快照
    UFUNCTION(BlueprintCallable, Category = "UAVMonitor")
    TArray<FUAVState> GetAllUAVStates() const { return CachedUAVStates; }

    // 手动强制刷新
    UFUNCTION(BlueprintCallable, Category = "UAVMonitor")
    void ForceUpdate();

private:
    void UpdateAllUAVStates();

    // 辅助：从Actor获取速度（km/h）
    float GetSpeedKmh(AActor* Actor);

    // 辅助：模拟电量（可根据飞行时间、距离等自定义）
    float GetSimulatedBattery(int32 UAVId);

    TArray<FUAVState> CachedUAVStates;

    // 记录上次刷新时间（用于模拟电量消耗）
    float LastUpdateTime;
};