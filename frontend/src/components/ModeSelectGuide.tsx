/**
 * 模式选择引导组件
 * 在上传前或处理前显示，根据LLM状态引导用户选择处理模式
 */

import React, { useState, useCallback } from 'react'
import {
  Modal,
  Button,
  Card,
  Tag,
  Space,
  Typography,
  Divider,
  Alert,
  Radio,
} from 'antd'
import {
  RobotOutlined,
  FileTextOutlined,
  EyeOutlined,
  AlertOutlined,
} from '@ant-design/icons'

import {
  useLLMConfig,
  useModeRecommendation,
  LLMConfigStatus,
  ProcessMode,
  ModeInfo,
  MODE_CONFIG,
} from '../hooks/useLLMConfig'

const { Title, Text, Paragraph } = Typography

interface ModeSelectGuideProps {
  visible: boolean
  onCancel: () => void
  onConfirm: (mode: ProcessMode) => void
  title?: string
  showBackToFull?: boolean
}

const ModeSelectGuide: React.FC<ModeSelectGuideProps> = ({
  visible,
  onCancel,
  onConfirm,
  title = '选择处理模式',
  showBackToFull = true,
}) => {
  const [selectedMode, setSelectedMode] = useState<ProcessMode | null>(null)
  const {
    configStatus,
    getStatusDisplay,
    getStatusMessage,
    shouldShowGuide,
  } = useLLMConfig()
  
  const { getRecommendation } = useModeRecommendation()
  
  const {
    recommended,
    alternatives,
    reason,
  } = getRecommendation()
  
  // 初始化默认选中
  React.useEffect(() => {
    if (visible && !selectedMode) {
      setSelectedMode(recommended.mode)
    }
  }, [visible, recommended.mode, selectedMode])
  
  const handleConfirm = useCallback(() => {
    if (selectedMode) {
      onConfirm(selectedMode)
    }
  }, [selectedMode, onConfirm])
  
  const renderModeCard = (modeInfo: ModeInfo, isRecommended: boolean) => {
    const iconMap: Record<string, React.ReactNode> = {
      [ProcessMode.AI_SMART]: <RobotOutlined style={{ fontSize: 32 }} />,
      [ProcessMode.SUBTITLE_ORGANIZED]: <FileTextOutlined style={{ fontSize: 32 }} />,
      [ProcessMode.QUICK_PREVIEW]: <EyeOutlined style={{ fontSize: 32 }} />,
      [ProcessMode.RAW_TRANSCRIPT]: <FileTextOutlined style={{ fontSize: 32 }} />,
    }
    
    const colorMap: Record<string, string> = {
      green: 'green',
      blue: 'blue',
      orange: 'orange',
      gray: 'default',
    }
    
    return (
      <Card
        key={modeInfo.mode}
        hoverable
        bordered={selectedMode === modeInfo.mode}
        onClick={() => setSelectedMode(modeInfo.mode)}
        style={{
          cursor: 'pointer',
          borderWidth: selectedMode === modeInfo.mode ? 2 : 1,
          borderColor: selectedMode === modeInfo.mode ? '#1890ff' : undefined,
        }}
        styles={{ body: { padding: 16 } }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            {iconMap[modeInfo.mode]}
            <Space direction="vertical" style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 16 }}>
                  {modeInfo.name}
                </Text>
                {modeInfo.badge && (
                  <Tag color={colorMap[modeInfo.badge_color]}>
                    {modeInfo.badge}
                  </Tag>
                )}
                {isRecommended && !modeInfo.recommended && (
                  <Tag color="blue">备选</Tag>
                )}
              </div>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {modeInfo.description}
              </Text>
            </Space>
          </Space>
          
          {modeInfo.capabilities.length > 0 && (
            <div>
              <Space wrap style={{ marginTop: 8 }}>
                {modeInfo.capabilities.map(cap => (
                  <Tag key={cap} size="small">
                    {cap}
                  </Tag>
                ))}
              </Space>
            </div>
          )}
          
          {modeInfo.is_demo && (
            <Alert
              type="warning"
              message="⚠️ 演示模式"
              description="此模式仅供预览效果，不代表正式AI智能识别"
              showIcon
              size="small"
            />
          )}
        </Space>
      </Card>
    )
  }
  
  const statusDisplay = getStatusDisplay()
  
  return (
    <Modal
      title={
        <Space>
          <span>{title}</span>
          <Tag color={statusDisplay.color} style={{ fontSize: 12 }}>
            {statusDisplay.icon} {statusDisplay.text}
          </Tag>
        </Space>
      }
      open={visible}
      onCancel={onCancel}
      width={720}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="confirm"
          type="primary"
          onClick={handleConfirm}
          disabled={!selectedMode}
        >
          确认选择
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 状态说明 */}
        <Alert
          type={configStatus?.status === LLMConfigStatus.CONFIGURED ? 'success' : 'info'}
          message={getStatusMessage()}
          description={reason}
          showIcon
        />
        
        {/* 推荐模式 */}
        <div>
          <Title level={5}>推荐模式</Title>
          {renderModeCard(recommended, true)}
        </div>
        
        {/* 备选模式 */}
        {alternatives.length > 0 && (
          <div>
            <Title level={5}>其他可选模式</Title>
            <Space direction="vertical" style={{ width: '100%' }}>
              {alternatives.map(mode => renderModeCard(mode, false))}
            </Space>
          </div>
        )}
        
        <Divider style={{ margin: 0 }} />
        
        {/* 提示 */}
        <Alert
          type="info"
          message="提示"
          description="处理模式选择后，系统会保存配置快照，确保历史任务不受后续配置变更影响"
          showIcon
        />
      </Space>
    </Modal>
  )
}

export default ModeSelectGuide

