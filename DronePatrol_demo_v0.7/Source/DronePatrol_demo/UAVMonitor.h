// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UAVMonitor.generated.h"

// ���˻�״̬�ṹ�壨��ͼ���ã�
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

// ״̬����ί�У�ע���Сд��FOnUAVStateUpdated��
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnUAVStateUpdated, const FUAVState&, NewState);

UCLASS(Blueprintable)
class DRONEPATROL_DEMO_API AUAVMonitor : public AActor
{
    GENERATED_BODY()

public:
    AUAVMonitor();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaTime) override;   // ����Tick���򵥿ɿ�

public:
    // UI�󶨵�ί��
    UPROPERTY(BlueprintAssignable, Category = "UAVMonitor")
    FOnUAVStateUpdated OnUAVStateUpdated;

    // ��ȡ����״̬����
    UFUNCTION(BlueprintCallable, Category = "UAVMonitor")
    TArray<FUAVState> GetAllUAVStates() const { return CachedUAVStates; }

    // �ֶ�ǿ��ˢ��
    UFUNCTION(BlueprintCallable, Category = "UAVMonitor")
    void ForceUpdate();

private:
    void UpdateAllUAVStates();

    // ��������Actor��ȡ�ٶȣ�km/h��
    float GetSpeedKmh(AActor* Actor);

    // ������ģ��������ɸ��ݷ���ʱ�䡢������Զ��壩
    float GetSimulatedBattery(int32 UAVId);

    TArray<FUAVState> CachedUAVStates;

    // ��¼�ϴ�ˢ��ʱ�䣨����ģ��������ģ�
    float LastUpdateTime;
};