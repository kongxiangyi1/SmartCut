/**
 * LLM配置状态Hook
 * 用于检测LLM配置状态，提供模式推荐和引导逻辑
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect } from 'react'
import { message } from 'antd'
import { api } from '../services/api'

// ============================================
// 类型定义
// ============================================

export enum LLMConfigStatus {
  NOT_CONFIGURED = 'not_configured',
  INVALID_KEY = 'invalid_key',
  SERVICE_UNAVAILABLE = 'service_unavailable',
  RATE_LIMITED = 'rate_limited',
  CONNECTION_FAILED = 'connection_failed',
  TIMEOUT = 'timeout',
  CONFIGURED = 'configured',
}

export enum ProcessMode {
  AI_SMART = 'ai_smart',
  SUBTITLE_ORGANIZED = 'subtitle_organized',
  QUICK_PREVIEW = 'quick_preview',
  RAW_TRANSCRIPT = 'raw_transcript',
}

export interface LLMStatusInfo {
  status: LLMConfigStatus
  message: string
  provider: string
  model: string
  available_modes: ProcessMode[]
  retry_after: number
  last_check: string
  is_available: boolean
}

export interface ModeInfo {
  mode: ProcessMode
  name: string
  short_name: string
  description: string
  badge: string
  badge_color: 'green' | 'blue' | 'orange' | 'gray'
  icon: string
  recommended: boolean
  requires_llm: boolean
  is_demo: boolean
  capabilities: string[]
}

// ============================================
// 模式配置
// ============================================

export const MODE_CONFIG: Record<ProcessMode, ModeInfo> = {
  [ProcessMode.AI_SMART]: {
    mode: ProcessMode.AI_SMART,
    name: 'AI智能模式',
    short_name: 'AI智能',
    description: '使用AI深度理解视频内容，生成精彩片段、智能标题和主题合集',
    badge: '推荐',
    badge_color: 'green',
    icon: '🤖',
    recommended: true,
    requires_llm: true,
    is_demo: false,
    capabilities: ['字幕生成', '大纲提取', '精彩片段', '智能标题', '主题聚类'],
  },
  [ProcessMode.SUBTITLE_ORGANIZED]: {
    mode: ProcessMode.SUBTITLE_ORGANIZED,
    name: '字幕整理模式',
    short_name: '字幕整理',
    description: '将字幕标准化整理，包括说话人标注和标点恢复，无AI分析',
    badge: '免费',
    badge_color: 'blue',
    icon: '📝',
    recommended: false,
    requires_llm: false,
    is_demo: false,
    capabilities: ['字幕生成', '说话人标注', '标点恢复'],
  },
  [ProcessMode.QUICK_PREVIEW]: {
    mode: ProcessMode.QUICK_PREVIEW,
    name: '快速预览',
    short_name: '预览',
    description: '仅供效果预览，使用基础算法模拟切片，不可用于正式业务',
    badge: '演示',
    badge_color: 'orange',
    icon: '👁️',
    recommended: false,
    requires_llm: false,
    is_demo: true,
    capabilities: ['字幕生成', '基础分段'],
  },
  [ProcessMode.RAW_TRANSCRIPT]: {
    mode: ProcessMode.RAW_TRANSCRIPT,
    name: '原始转录',
    short_name: '原始',
    description: '仅输出语音转写的原始文本，无任何处理',
    badge: '基础',
    badge_color: 'gray',
    icon: '📄',
    recommended: false,
    requires_llm: false,
    is_demo: false,
    capabilities: ['字幕生成'],
  },
}

// ============================================
// API调用
// ============================================

const fetchLLMConfigStatus = async (): Promise<LLMStatusInfo> => {
  const response = await api.get<LLMStatusInfo>('/settings/llm-config-status')
  return response.data
}

const fetchAllModes = async (): Promise<ModeInfo[]> => {
  const response = await api.get<ModeInfo[]>('/settings/process-modes')
  return response.data
}

// ============================================
// Hook定义
// ============================================

export const useLLMConfig = (options?: {
  refetchInterval?: number
  onStatusChange?: (newStatus: LLMStatusInfo, oldStatus?: LLMStatusInfo) => void
}) => {
  const queryClient = useQueryClient()

  // 查询LLM配置状态
  const {
    data: configStatus,
    isLoading: isLoadingStatus,
    isError: isErrorStatus,
    error: statusError,
    refetch: refetchStatus,
  } = useQuery<LLMStatusInfo, Error>({
    queryKey: ['llm-config-status'],
    queryFn: fetchLLMConfigStatus,
    staleTime: 10000, // 10秒内不重复请求
    refetchInterval: options?.refetchInterval ?? 30000, // 默认30秒刷新
    retry: 2,
  })

  // 查询所有可用模式
  const {
    data: allModes,
    isLoading: isLoadingModes,
  } = useQuery<ModeInfo[], Error>({
    queryKey: ['process-modes'],
    queryFn: fetchAllModes,
    staleTime: 60000, // 1分钟内不重复请求
  })

  // 状态变化检测
  useEffect(() => {
    if (options?.onStatusChange && configStatus) {
      const previousStatus = queryClient.getQueryData<LLMStatusInfo>(['llm-config-status'])
      if (previousStatus && previousStatus.status !== configStatus.status) {
        options.onStatusChange(configStatus, previousStatus)
      }
    }
  }, [configStatus, options?.onStatusChange])

  /**
   * 判断当前状态是否表示LLM可用
   */
  const isAvailable = useCallback((): boolean => {
    return configStatus?.status === LLMConfigStatus.CONFIGURED
  }, [configStatus])

  /**
   * 判断是否需要显示模式选择引导
   */
  const shouldShowGuide = useCallback((): boolean => {
    if (!configStatus) return false
    return configStatus.status !== LLMConfigStatus.CONFIGURED
  }, [configStatus])

  /**
   * 获取推荐的模式
   */
  const getRecommendedMode = useCallback((): ModeInfo => {
    if (!configStatus) {
      return MODE_CONFIG[ProcessMode.RAW_TRANSCRIPT]
    }

    switch (configStatus.status) {
      case LLMConfigStatus.CONFIGURED:
        return MODE_CONFIG[ProcessMode.AI_SMART]
      case LLMConfigStatus.RATE_LIMITED:
      case LLMConfigStatus.SERVICE_UNAVAILABLE:
        return MODE_CONFIG[ProcessMode.SUBTITLE_ORGANIZED]
      case LLMConfigStatus.INVALID_KEY:
      case LLMConfigStatus.NOT_CONFIGURED:
      case LLMConfigStatus.CONNECTION_FAILED:
      case LLMConfigStatus.TIMEOUT:
        return MODE_CONFIG[ProcessMode.SUBTITLE_ORGANIZED]
      default:
        return MODE_CONFIG[ProcessMode.RAW_TRANSCRIPT]
    }
  }, [configStatus])

  /**
   * 获取可用模式列表（根据LLM状态过滤）
   */
  const getAvailableModes = useCallback((): ModeInfo[] => {
    if (!configStatus) {
      return [MODE_CONFIG[ProcessMode.RAW_TRANSCRIPT]]
    }

    const availableModes: ModeInfo[] = []

    if (configStatus.status === LLMConfigStatus.CONFIGURED) {
      availableModes.push(MODE_CONFIG[ProcessMode.AI_SMART])
    }

    availableModes.push(MODE_CONFIG[ProcessMode.SUBTITLE_ORGANIZED])
    availableModes.push(MODE_CONFIG[ProcessMode.QUICK_PREVIEW])
    availableModes.push(MODE_CONFIG[ProcessMode.RAW_TRANSCRIPT])

    return availableModes
  }, [configStatus])

  /**
   * 获取状态友好的显示文本
   */
  const getStatusDisplay = useCallback((): {
    color: 'green' | 'orange' | 'red' | 'gray'
    text: string
    icon: string
  } => {
    if (!configStatus) {
      return { color: 'gray', text: '加载中...', icon: '⏳' }
    }

    switch (configStatus.status) {
      case LLMConfigStatus.CONFIGURED:
        return { color: 'green', text: '已配置', icon: '✅' }
      case LLMConfigStatus.NOT_CONFIGURED:
        return { color: 'orange', text: '未配置', icon: '⚠️' }
      case LLMConfigStatus.INVALID_KEY:
        return { color: 'red', text: '配置无效', icon: '❌' }
      case LLMConfigStatus.RATE_LIMITED:
        return { color: 'orange', text: '配额用完', icon: '⏰' }
      case LLMConfigStatus.SERVICE_UNAVAILABLE:
        return { color: 'red', text: '服务不可用', icon: '🚫' }
      case LLMConfigStatus.CONNECTION_FAILED:
        return { color: 'red', text: '连接失败', icon: '🔌' }
      case LLMConfigStatus.TIMEOUT:
        return { color: 'orange', text: '响应超时', icon: '⏱️' }
      default:
        return { color: 'gray', text: '未知', icon: '❓' }
    }
  }, [configStatus])

  /**
   * 获取状态提示消息
   */
  const getStatusMessage = useCallback((): string => {
    if (!configStatus) return '正在检查LLM配置...'

    switch (configStatus.status) {
      case LLMConfigStatus.CONFIGURED:
        return 'AI模型已配置并可用，可以使用完整功能'
      case LLMConfigStatus.NOT_CONFIGURED:
        return 'AI模型未配置，部分功能将不可用'
      case LLMConfigStatus.INVALID_KEY:
        return 'AI模型API密钥无效，请重新配置'
      case LLMConfigStatus.RATE_LIMITED:
        const retryIn = Math.ceil(configStatus.retry_after / 3600)
        return `AI模型配额已用完，预计${retryIn}小时后重置`
      case LLMConfigStatus.SERVICE_UNAVAILABLE:
        return 'AI模型服务暂时不可用，请稍后再试'
      case LLMConfigStatus.CONNECTION_FAILED:
        return '无法连接到AI模型服务，请检查网络连接'
      case LLMConfigStatus.TIMEOUT:
        return 'AI模型响应超时，请稍后再试'
      default:
        return 'LLM配置状态未知'
    }
  }, [configStatus])

  /**
   * 手动刷新状态
   */
  const refresh = useCallback(async () => {
    try {
      await refetchStatus()
      message.success('LLM配置状态已刷新')
    } catch (error) {
      message.error('刷新失败，请稍后重试')
    }
  }, [refetchStatus])

  return {
    // 数据
    configStatus,
    allModes,

    // 加载状态
    isLoading: isLoadingStatus || isLoadingModes,
    isError: isErrorStatus,
    error: statusError,

    // 判断方法
    isAvailable,
    shouldShowGuide,
    getRecommendedMode,
    getAvailableModes,
    getStatusDisplay,
    getStatusMessage,

    // 操作方法
    refresh,

    // 原始配置信息
    provider: configStatus?.provider,
    model: configStatus?.model,
    availableModes: configStatus?.available_modes ?? [],
  }
}

// ============================================
// 便捷Hook：用于上传前检查
// ============================================

export const useUploadCheck = () => {
  const { configStatus, shouldShowGuide, getRecommendedMode, isLoading } = useLLMConfig()

  const checkBeforeUpload = useCallback(async (): Promise<{
    shouldShow: boolean
    recommendedMode: ProcessMode
    status: LLMStatusInfo | undefined
  }> => {
    if (isLoading) {
      return {
        shouldShow: false,
        recommendedMode: ProcessMode.AI_SMART,
        status: undefined,
      }
    }

    const showGuide = shouldShowGuide()
    const recommended = getRecommendedMode()

    return {
      shouldShow: showGuide,
      recommendedMode: recommended.mode,
      status: configStatus,
    }
  }, [configStatus, shouldShowGuide, getRecommendedMode, isLoading])

  return {
    checkBeforeUpload,
    configStatus,
    isLoading,
  }
}

// ============================================
// 便捷Hook：用于模式推荐
// ============================================

export const useModeRecommendation = () => {
  const { getRecommendedMode, getAvailableModes, isAvailable } = useLLMConfig()

  const getRecommendation = useCallback((): {
    recommended: ModeInfo
    alternatives: ModeInfo[]
    reason: string
  } => {
    const recommended = getRecommendedMode()
    const allAvailable = getAvailableModes()
    const alternatives = allAvailable.filter(m => m.mode !== recommended.mode)

    let reason = ''
    if (recommended.mode === ProcessMode.AI_SMART) {
      reason = 'AI模型已配置，使用此模式可获得最佳处理效果'
    } else if (recommended.mode === ProcessMode.SUBTITLE_ORGANIZED) {
      reason = 'AI模型不可用，此模式可在不消耗AI配额的情况下整理字幕'
    } else {
      reason = '请根据需要选择处理模式'
    }

    return {
      recommended,
      alternatives,
      reason,
    }
  }, [getRecommendedMode, getAvailableModes])

  return {
    getRecommendation,
    isAIAvailable: isAvailable(),
  }
}

