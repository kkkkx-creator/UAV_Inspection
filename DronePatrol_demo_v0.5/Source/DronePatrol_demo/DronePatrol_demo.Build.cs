// Fill out your copyright notice in the Description page of Project Settings.

using UnrealBuildTool;

public class DronePatrol_demo : ModuleRules
{
	public DronePatrol_demo(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"AirSim"
		});

		PrivateDependencyModuleNames.AddRange(new string[] {
			"UMG",
			"Slate",
			"SlateCore"
		});

        // 添加 AirSim 头文件的公开路径（关键！）
        PublicIncludePaths.AddRange(new string[] {
            System.IO.Path.GetFullPath(Target.RelativeEnginePath) + "Plugins/AirSim/Source"
        });

        // Uncomment if you are using Slate UI
        // PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

        // Uncomment if you are using online features
        // PrivateDependencyModuleNames.Add("OnlineSubsystem");

        // To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
    }
}
