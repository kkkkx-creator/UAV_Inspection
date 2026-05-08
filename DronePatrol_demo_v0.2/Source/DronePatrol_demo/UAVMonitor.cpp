// Fill out your copyright notice in the Description page of Project Settings.

#include "UAVMonitor.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "DrawDebugHelpers.h"

AUAVMonitor::AUAVMonitor()
{
    PrimaryActorTick.bCanEverTick = true;   // 启用Tick
    LastUpdateTime = 0.0f;
}

void AUAVMonitor::BeginPlay()
{
    Super::BeginPlay();
    LastUpdateTime = GetWorld()->GetTimeSeconds();
}

void AUAVMonitor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Super::EndPlay(EndPlayReason);
}

void AUAVMonitor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    // 每隔 0.5 秒更新一次状态（降低频率）
    float Now = GetWorld()->GetTimeSeconds();
    if (Now - LastUpdateTime >= 0.5f)
    {
        UpdateAllUAVStates();
        LastUpdateTime = Now;
    }
}

void AUAVMonitor::ForceUpdate()
{
    UpdateAllUAVStates();
}

void AUAVMonitor::UpdateAllUAVStates()
{
    UWorld* World = GetWorld();
    if (!World) return;

    // 获取场景中所有 Pawn（AirSim 无人机本质是 Pawn）
    TArray<AActor*> AllPawns;
    UGameplayStatics::GetAllActorsOfClass(World, APawn::StaticClass(), AllPawns);

    // 过滤出无人机（假设无人机名称包含 "UAV" 或 "Drone"，可按需调整）
    TArray<AActor*> Drones;
    for (AActor* Actor : AllPawns)
    {
        FString Name = Actor->GetName();
        if (Name.Contains(TEXT("UAV")) || Name.Contains(TEXT("Drone")) || Name.Contains(TEXT("Quad")))
        {
            Drones.Add(Actor);
        }
    }

    // 如果没有找到任何无人机，尝试获取所有 Pawn（AirSim 可能命名为 BP_FlyingPawn_C 等）
    if (Drones.Num() == 0)
    {
        Drones = AllPawns;
    }

    // 重新构建状态数组
    CachedUAVStates.Empty();
    int32 Id = 1;
    for (AActor* Drone : Drones)
    {
        FUAVState State;
        State.UAVId = Id++;
        State.Position = Drone->GetActorLocation();

        // 获取速度（从移动组件或 Velocity 属性）
        State.SpeedKmh = GetSpeedKmh(Drone);

        // 模拟电量（根据示例动态变化）
        State.BatteryPercent = GetSimulatedBattery(State.UAVId);

        // ------ 这里可以从你的任务管理模块获取真实任务状态 ------
        // 目前提供模拟数据
        State.TaskStatus = TEXT("En Route");
        State.TaskType = (State.UAVId % 2 == 0) ? TEXT("Line") : TEXT("Point");
        State.TaskProgress = FMath::Frac(GetWorld()->GetTimeSeconds() * 0.1f + State.UAVId); // 动态进度

        // ------ 故障检测 ------
        State.bHasFault = false;
        State.FaultType = TEXT("");
        if (State.BatteryPercent < 15.0f)
        {
            State.bHasFault = true;
            State.FaultType = TEXT("Low Battery");
        }
        else if (State.SpeedKmh > 80.0f)
        {
            State.bHasFault = true;
            State.FaultType = TEXT("Excessive Speed");
        }
        else if (FMath::FRand() < 0.005f) // 随机演示故障
        {
            State.bHasFault = true;
            State.FaultType = TEXT("Motor Stutter");
        }

        CachedUAVStates.Add(State);
        OnUAVStateUpdated.Broadcast(State);
    }
}

float AUAVMonitor::GetSpeedKmh(AActor* Actor)
{
    if (!Actor) return 0.0f;

    FVector Velocity = FVector::ZeroVector;
    // 尝试获取移动组件速度
    if (APawn* Pawn = Cast<APawn>(Actor))
    {
        if (Pawn->GetMovementComponent())
        {
            Velocity = Pawn->GetMovementComponent()->Velocity;
        }
        else
        {
            Velocity = Pawn->GetVelocity();
        }
    }
    else
    {
        Velocity = Actor->GetVelocity();
    }
    float SpeedMPS = Velocity.Size();
    return SpeedMPS * 3.6f; // 转换为 km/h
}

float AUAVMonitor::GetSimulatedBattery(int32 UAVId)
{
    // 简单模拟：电量随任务时间线性下降，且每个无人机略有不同
    float Time = GetWorld()->GetTimeSeconds();
    float BaseBattery = 100.0f - FMath::Fmod(Time * 0.5f + UAVId * 10.0f, 100.0f);
    return FMath::Clamp(BaseBattery, 0.0f, 100.0f);
}