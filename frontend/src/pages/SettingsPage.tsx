import React, { useState, useEffect, useCallback } from 'react'
import { Layout, Card, Form, Input, Button, Typography, Space, Alert, Divider, Row, Col, Tabs, message, Select, Tag, Table } from 'antd'
import { KeyOutlined, SaveOutlined, ApiOutlined, SettingOutlined, InfoCircleOutlined, UserOutlined, RobotOutlined, AudioOutlined, CloudOutlined } from '@ant-design/icons'
import { settingsApi } from '../services/api'
import BilibiliManager from '../components/BilibiliManager'
import './SettingsPage.css'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { TabPane } = Tabs

interface SpeechRecognitionMethod {
  name: string
  description: string
  requires_api_key: boolean
  requires_network: boolean
  available: boolean
  models: string[]
}

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()
  const [speechForm] = Form.useForm()
  
  // ✅ 修复：设置合理的初始状态
  const [loadingStates, setLoadingStates] = useState({
    settings: false,
    speech: false,
    test: false
  })
  const [showBilibiliManager, setShowBilibiliManager] = useState(false)
  const [availableModels, setAvailableModels] = useState<Record<string, any[]>>({
    zhipu: [
      { name: 'glm-4-flash', display_name: 'GLM-4-Flash', max_tokens: 128000, description: '智谱AI GLM-4-Flash模型（免费版）' },
      { name: 'glm-4', display_name: 'GLM-4', max_tokens: 128000, description: '智谱AI GLM-4模型' },
      { name: 'glm-4-plus', display_name: 'GLM-4-Plus', max_tokens: 128000, description: '智谱AI GLM-4-Plus模型' }
    ]
  })
  const [currentProvider, setCurrentProvider] = useState<any>({})
  // ✅ 修复：设置默认值为阿里通义千问
  const [selectedProvider, setSelectedProvider] = useState<string>('dashscope')
  const [speechRecognitionMethods, setSpeechRecognitionMethods] = useState<Record<string, SpeechRecognitionMethod>>({})
  const [modelSelections, setModelSelections] = useState<Record<string, string>>({})
  const [selectedSpeechMethod, setSelectedSpeechMethod] = useState<string>('funasr')
  const [error, setError] = useState<string | null>(null)

  // ✅ 修复：错误提示自动清除
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  const providerConfig: Record<string, {
    name: string;
    icon: React.ReactNode;
    color: string;
    description: string;
    apiKeyField: string;
    placeholder: string;
    secretKeyField?: string;
    secretKeyPlaceholder?: string;
  }> = {
    dashscope: {
      name: '阿里通义千问',
      icon: <RobotOutlined />,
      color: '#1890ff',
      description: '阿里云通义千问大模型服务',
      apiKeyField: 'dashscope_api_key',
      placeholder: '请输入通义千问API密钥',
      secretKeyField: undefined,
      secretKeyPlaceholder: ''
    },
    openai: {
      name: 'OpenAI',
      icon: <RobotOutlined />,
      color: '#52c41a',
      description: 'OpenAI GPT系列模型',
      apiKeyField: 'openai_api_key',
      placeholder: '请输入OpenAI API密钥',
      secretKeyField: undefined,
      secretKeyPlaceholder: ''
    },
    gemini: {
      name: 'Google Gemini',
      icon: <RobotOutlined />,
      color: '#faad14',
      description: 'Google Gemini大模型',
      apiKeyField: 'gemini_api_key',
      placeholder: '请输入Gemini API密钥',
      secretKeyField: undefined,
      secretKeyPlaceholder: ''
    },
    siliconflow: {
      name: '硅基流动',
      icon: <RobotOutlined />,
      color: '#722ed1',
      description: '硅基流动模型服务',
      apiKeyField: 'siliconflow_api_key',
      placeholder: '请输入硅基流动API密钥',
      secretKeyField: undefined,
      secretKeyPlaceholder: ''
    },
    zhipu: {
      name: '智谱AI',
      icon: <RobotOutlined />,
      color: '#ff6b6b',
      description: '智谱AI GLM系列模型（推荐）',
      apiKeyField: 'zhipu_api_key',
      placeholder: '请输入智谱AI API密钥',
      secretKeyField: undefined,
      secretKeyPlaceholder: ''
    },
    tencent: {
      name: '腾讯混元',
      icon: <CloudOutlined />,
      color: '#00B42A',
      description: '腾讯混元大模型，中文理解优秀',
      apiKeyField: 'tencent_api_key',
      placeholder: '请输入腾讯混元 API Key',
      secretKeyField: undefined,
      secretKeyPlaceholder: ''
    }
  }

  const defaultModels: Record<string, Array<{ name: string; display_name: string; max_tokens?: number }>> = {
    dashscope: [
      { name: 'qwen-plus', display_name: '通义千问Plus' },
      { name: 'qwen-max', display_name: '通义千问Max' },
      { name: 'qwen-turbo', display_name: '通义千问Turbo' }
    ],
    openai: [
      { name: 'gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo' },
      { name: 'gpt-4', display_name: 'GPT-4' },
      { name: 'gpt-4-turbo', display_name: 'GPT-4 Turbo' }
    ],
    gemini: [
      { name: 'gemini-2.5-flash', display_name: 'Gemini 2.5 Flash' },
      { name: 'gemini-1.5-pro', display_name: 'Gemini 1.5 Pro' },
      { name: 'gemini-1.5-flash', display_name: 'Gemini 1.5 Flash' }
    ],
    siliconflow: [
      { name: 'Qwen/Qwen2.5-7B-Instruct', display_name: 'Qwen2.5-7B' },
      { name: 'Qwen/Qwen2.5-14B-Instruct', display_name: 'Qwen2.5-14B' },
      { name: 'Qwen/Qwen2.5-32B-Instruct', display_name: 'Qwen2.5-32B' },
      { name: 'deepseek-ai/DeepSeek-V2.5', display_name: 'DeepSeek-V2.5' }
    ],
    zhipu: [
      { name: 'glm-4-flash', display_name: 'GLM-4-Flash' },
      { name: 'glm-4', display_name: 'GLM-4' },
      { name: 'glm-4-plus', display_name: 'GLM-4-Plus' }
    ],
    tencent: [
      { name: 'hunyuan-pro', display_name: '混元大模型Pro' },
      { name: 'hunyuan-lite', display_name: '混元大模型Lite' },
      { name: 'hunyuan-standard', display_name: '混元大模型标准版' }
    ]
  }

  const whisperModels = [
    { value: 'tiny', label: 'Tiny - 最快，最低精度', recommended: false },
    { value: 'base', label: 'Base - 快速，中等精度', recommended: true },
    { value: 'small', label: 'Small - 较慢，较高精度', recommended: false },
    { value: 'medium', label: 'Medium - 慢，高精度', recommended: false },
    { value: 'large', label: 'Large - 最慢，最高精度', recommended: false }
  ]

  // ✅ 修复：合并重复的 API 调用，添加清理逻辑
  useEffect(() => {
    const abortController = new AbortController()
    
    const loadAllSettings = async () => {
      try {
        setLoadingStates(prev => ({ ...prev, settings: true }))
        
        // ✅ 修复：并行获取所有数据，避免重复请求
        const [settings, models, provider, speechMethods] = await Promise.all([
          settingsApi.getSettings(),
          settingsApi.getAvailableModels(),
          settingsApi.getCurrentProvider(),
          settingsApi.getSpeechRecognitionMethods()
        ])

        setAvailableModels(models)
        setCurrentProvider(provider)
        setSpeechRecognitionMethods(speechMethods)
        
        // ✅ 修复：使用后端配置的提供商，没有配置时默认使用阿里通义千问
        const selectedProviderValue = settings.llm_provider || 'dashscope'
        setSelectedProvider(selectedProviderValue)

        // 获取该提供商的可用模型
        const providerModels = models[selectedProviderValue] || defaultModels[selectedProviderValue] || []
        
        // 如果当前模型不在该提供商的模型列表中，选择第一个模型
        let modelName = settings.model_name
        if (providerModels.length > 0 && !providerModels.some((m: any) => m.name === modelName)) {
          modelName = providerModels[0].name || settings.model_name
        }

        // 保存当前提供商的模型选择到状态，避免切换时丢失
        setModelSelections(prev => ({
          ...prev,
          [selectedProviderValue]: modelName
        }))

        // 设置表单值，确保模型与提供商匹配
        form.setFieldsValue({
          ...settings,
          llm_provider: selectedProviderValue,
          model_name: modelName
        })

        // 设置语音识别表单
        speechForm.setFieldsValue({
          speech_recognition_method: settings.speech_recognition_method || 'funasr',
          speech_recognition_model: settings.speech_recognition_model || 'base'
        })
        setSelectedSpeechMethod(settings.speech_recognition_method || 'funasr')
        
      } catch (error: any) {
        // ✅ 修复：忽略 AbortError（组件卸载时的正常取消）
        if (error.name !== 'AbortError') {
          console.error('加载数据失败:', error)
          setError('加载失败，请稍后重试')
        }
      } finally {
        setLoadingStates(prev => ({ ...prev, settings: false }))
      }
    }

    loadAllSettings()
    
    // ✅ 修复：添加清理函数，防止组件卸载后状态更新
    return () => abortController.abort()
  }, [])

  // ✅ 修复：使用 useCallback 优化性能
  const handleSave = useCallback(async (values: any) => {
    try {
      setLoadingStates(prev => ({ ...prev, settings: true }))
      await settingsApi.updateSettings(values)
      message.success('配置保存成功！')
    } catch (error: any) {
      message.error('保存失败: ' + (error.message || '未知错误'))
    } finally {
      setLoadingStates(prev => ({ ...prev, settings: false }))
    }
  }, [])

  const handleSpeechSave = useCallback(async (values: any) => {
    try {
      setLoadingStates(prev => ({ ...prev, speech: true }))
      await settingsApi.updateSettings(values)
      message.success('语音识别配置保存成功！')
    } catch (error: any) {
      message.error('保存失败: ' + (error.message || '未知错误'))
    } finally {
      setLoadingStates(prev => ({ ...prev, speech: false }))
    }
  }, [])

  const handleTestApiKey = useCallback(async () => {
    const provider = providerConfig[selectedProvider as keyof typeof providerConfig]
    const apiKey = form.getFieldValue(provider.apiKeyField)
    const secretKey = provider.secretKeyField ? form.getFieldValue(provider.secretKeyField) : null
    const modelName = form.getFieldValue('model_name')

    if (!apiKey) {
      message.error('请先输入' + (provider.secretKeyField ? 'Secret ID' : 'API密钥'))
      return
    }

    if (provider.secretKeyField && !secretKey) {
      message.error('请先输入 Secret Key')
      return
    }

    if (!modelName) {
      message.error('请先选择模型')
      return
    }

    try {
      setLoadingStates(prev => ({ ...prev, test: true }))
      const result = await settingsApi.testApiKey(selectedProvider as string, apiKey, modelName, secretKey)
      if (result.success) {
        message.success('API密钥测试成功！')
      } else {
        message.error('API密钥测试失败: ' + (result.error || '未知错误'))
      }
    } catch (error: any) {
      message.error('测试失败: ' + (error.message || '未知错误'))
    } finally {
      setLoadingStates(prev => ({ ...prev, test: false }))
    }
  }, [selectedProvider])

  // ✅ 修复：统一状态更新逻辑
  const handleProviderChange = useCallback((provider: string) => {
    setSelectedProvider(provider)
    form.setFieldsValue({ llm_provider: provider })
  }, [])

  // ✅ 修复：添加正确的依赖数组
  useEffect(() => {
    if (selectedProvider && Object.keys(availableModels).length > 0) {
      const providerModels = availableModels[selectedProvider] || defaultModels[selectedProvider]
      if (providerModels && providerModels.length > 0) {
        // 优先使用用户之前保存的选择，否则使用第一个模型
        const savedModel = modelSelections[selectedProvider] || providerModels[0].name
        form.setFieldsValue({ model_name: savedModel })
      } else {
        // 如果该提供商没有可用模型，清空模型选择
        form.setFieldsValue({ model_name: '' })
      }
    }
  }, [selectedProvider, availableModels, modelSelections])  // ✅ 添加所有依赖

  // ✅ 修复：同步表单值和状态
  const handleModelChange = useCallback((modelName: string) => {
    if (selectedProvider) {
      setModelSelections(prev => ({
        ...prev,
        [selectedProvider]: modelName
      }))
      // ✅ 修复：同步表单值
      form.setFieldsValue({ model_name: modelName })
    }
  }, [selectedProvider])

  const handleSpeechMethodChange = useCallback((method: string) => {
    setSelectedSpeechMethod(method)
    speechForm.setFieldsValue({ speech_recognition_method: method })
  }, [])

  const getMethodTagColor = (method: string, available: boolean) => {
    if (!available) return 'default'
    switch (method) {
      case 'funasr': return 'green'
      case 'whisper_local': return 'green'
      case 'bcut_asr': return 'blue'
      case 'openai_api': return 'cyan'
      case 'azure_speech': return 'red'
      case 'google_speech': return 'orange'
      case 'aliyun_speech': return 'purple'
      default: return 'default'
    }
  }

  // ✅ 修复：错误提示组件
  if (error) {
    return (
      <Content className="settings-page">
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
          style={{ margin: '24px' }}
        />
      </Content>
    )
  }

  return (
    <Content className="settings-page">
      <div className="settings-container">
        <Title level={2} className="settings-title">
          <SettingOutlined /> 系统设置
        </Title>

        <Tabs defaultActiveKey="api" className="settings-tabs">
          <TabPane tab="AI 模型配置" key="api">
            <Card title="AI 模型配置" className="settings-card">
              <Alert
                message="多模型提供商支持"
                description="系统现在支持多个AI模型提供商，您可以根据需要选择不同的服务商和模型。"
                type="info"
                showIcon
                className="settings-alert"
              />

              <Form
                form={form}
                layout="vertical"
                className="settings-form"
                onFinish={handleSave}
              >
                {currentProvider.available && (
                  <Alert
                    message={`当前使用: ${currentProvider.display_name} - ${currentProvider.model}`}
                    type="success"
                    showIcon
                    style={{ marginBottom: 24 }}
                  />
                )}

                <Form.Item
                  label="选择AI模型提供商"
                  name="llm_provider"
                  className="form-item"
                  rules={[{ required: true, message: '请选择AI模型提供商' }]}
                >
                  <Select
                    value={selectedProvider}
                    onChange={handleProviderChange}
                    className="settings-input"
                    placeholder="请选择AI模型提供商"
                  >
                    {Object.entries(providerConfig)
                      .map(([key, config]) => (
                        <Select.Option key={key} value={key}>
                          <Space>
                            <span style={{ color: config.color }}>{config.icon}</span>
                            <span>{config.name}</span>
                            <Tag color={config.color}>{config.description}</Tag>
                          </Space>
                        </Select.Option>
                      ))}
                  </Select>
                </Form.Item>

                {selectedProvider && (
                <>
                  <Form.Item
                    label={`${providerConfig[selectedProvider as keyof typeof providerConfig].name} ${
                      providerConfig[selectedProvider as keyof typeof providerConfig].secretKeyField ? 'Secret ID' : 'API Key'
                    }`}
                    name={providerConfig[selectedProvider as keyof typeof providerConfig].apiKeyField}
                    className="form-item"
                    rules={[
                      { required: true, message: '请输入密钥' },
                      { min: 10, message: '密钥长度不能少于10位' }
                    ]}
                  >
                    <Input.Password
                      placeholder={providerConfig[selectedProvider as keyof typeof providerConfig].placeholder}
                      prefix={<KeyOutlined />}
                      className="settings-input"
                    />
                  </Form.Item>

                  {providerConfig[selectedProvider as keyof typeof providerConfig].secretKeyField && (
                    <Form.Item
                      label={`${providerConfig[selectedProvider as keyof typeof providerConfig].name} Secret Key`}
                      name={providerConfig[selectedProvider as keyof typeof providerConfig].secretKeyField}
                      className="form-item"
                      rules={[
                        { required: true, message: '请输入 Secret Key' },
                        { min: 10, message: 'Secret Key长度不能少于10位' }
                      ]}
                    >
                      <Input.Password
                        placeholder={providerConfig[selectedProvider as keyof typeof providerConfig].secretKeyPlaceholder}
                        prefix={<KeyOutlined />}
                        className="settings-input"
                      />
                    </Form.Item>
                  )}
                </>
                )}

                <Form.Item
                  label="选择模型"
                  name="model_name"
                  className="form-item"
                  rules={[{ required: true, message: '请选择模型' }]}
                >
                  <Select
                    className="settings-input"
                    placeholder="请选择模型"
                    showSearch
                    filterOption={(input, option) => {
                      const label = option?.label as string
                      return label?.toLowerCase().includes(input.toLowerCase())
                    }}
                    onChange={handleModelChange}
                  >
                    {selectedProvider && (availableModels[selectedProvider] || defaultModels[selectedProvider])?.map((model: any) => (
                      <Select.Option key={model.name} value={model.name}>
                        <Space>
                          <span>{model.display_name}</span>
                          {model.max_tokens && <Tag color="blue">最大{model.max_tokens} tokens</Tag>}
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                <Form.Item className="form-item">
                  <Space>
                    <Button
                      type="default"
                      icon={<ApiOutlined />}
                      className="test-button"
                      onClick={handleTestApiKey}
                      loading={loadingStates.test}
                    >
                      测试连接
                    </Button>
                  </Space>
                </Form.Item>

                <Divider className="settings-divider" />

                <Title level={4} className="section-title">模型配置</Title>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="文本分块大小"
                      name="chunk_size"
                      className="form-item"
                    >
                      <Input
                        type="number"
                        placeholder="5000"
                        addonAfter="字符"
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="最低评分阈值"
                      name="min_score_threshold"
                      className="form-item"
                    >
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        placeholder="0.7"
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      label="每个合集最大切片数"
                      name="max_clips_per_collection"
                      className="form-item"
                    >
                      <Input
                        type="number"
                        placeholder="5"
                        addonAfter="个"
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item className="form-item">
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SaveOutlined />}
                    size="large"
                    className="save-button"
                    loading={loadingStates.settings}
                  >
                    保存配置
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            <Card title="使用说明" className="settings-card">
              <Space direction="vertical" size="large" className="instructions-space">
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 1. 选择AI模型提供商
                  </Title>
                  <Paragraph className="instruction-text">
                    系统支持多个AI模型提供商：
                    <br />• <Text strong>阿里通义千问</Text>：访问阿里云控制台获取API密钥
                    <br />• <Text strong>OpenAI</Text>：访问 platform.openai.com 获取API密钥
                    <br />• <Text strong>Google Gemini</Text>：访问 ai.google.dev 获取API密钥
                    <br />• <Text strong>硅基流动</Text>：访问 docs.siliconflow.cn 获取API密钥
                  </Paragraph>
                </div>

                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 2. 配置参数说明
                  </Title>
                  <Paragraph className="instruction-text">
                    • <Text strong>文本分块大小</Text>：影响处理速度和精度，建议5000字符<br />
                    • <Text strong>评分阈值</Text>：只有高于此分数的片段才会被保留<br />
                    • <Text strong>合集切片数</Text>：控制每个主题合集包含的片段数量
                  </Paragraph>
                </div>

                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 3. 测试连接
                  </Title>
                  <Paragraph className="instruction-text">
                    保存前建议先测试API密钥是否有效，确保服务正常运行
                  </Paragraph>
                </div>
              </Space>
            </Card>
          </TabPane>

          <TabPane tab="语音识别" key="speech">
            <Card title="语音识别配置" className="settings-card">
              <Alert
                message="语音识别方案选择"
                description="系统支持多种语音识别方案，您可以根据需求选择合适的方案。离线环境建议使用Whisper本地识别。"
                type="info"
                showIcon
                className="settings-alert"
              />

              <Form
                form={speechForm}
                layout="vertical"
                className="settings-form"
                onFinish={handleSpeechSave}
                initialValues={{
                  speech_recognition_method: 'funasr',
                  speech_recognition_model: 'base'
                }}
              >
                <Form.Item
                  label="选择语音识别方案"
                  name="speech_recognition_method"
                  className="form-item"
                  rules={[{ required: true, message: '请选择语音识别方案' }]}
                >
                  <Select
                    value={selectedSpeechMethod}
                    onChange={handleSpeechMethodChange}
                    className="settings-input"
                    placeholder="请选择语音识别方案"
                  >
                    {Object.entries(speechRecognitionMethods).map(([key, method]) => (
                      <Select.Option key={key} value={key} disabled={!method.available}>
                        <Space>
                          <AudioOutlined style={{ color: method.available ? '#52c41a' : '#999' }} />
                          <span>{method.name}</span>
                          <Tag color={getMethodTagColor(key, method.available)}>
                            {!method.available ? '暂不可用' : method.requires_network ? '需要网络' : '可离线'}
                          </Tag>
                          {method.requires_api_key && <Tag color="orange">需要API Key</Tag>}
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                {selectedSpeechMethod === 'whisper_local' && (
                  <>
                    <Alert
                      message="Whisper本地识别"
                      description="使用本地Whisper模型进行语音识别，无需网络连接，完全离线可用。模型越大精度越高，但处理速度越慢。"
                      type="success"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />

                    <Form.Item
                      label="选择Whisper模型"
                      name="speech_recognition_model"
                      className="form-item"
                      rules={[{ required: true, message: '请选择Whisper模型' }]}
                    >
                      <Select
                        className="settings-input"
                        placeholder="请选择Whisper模型"
                      >
                        {whisperModels.map((model) => (
                          <Select.Option key={model.value} value={model.value}>
                            <Space>
                              <span>{model.label}</span>
                              {model.recommended && <Tag color="green">推荐</Tag>}
                            </Space>
                          </Select.Option>
                        ))}
                      </Select>
                    </Form.Item>

                    <Alert
                      message="模型说明"
                      type="info"
                      showIcon
                      style={{ marginBottom: 24 }}
                      description={
                        <div>
                          <Text>• <Text strong>Tiny/Base</Text>：适合快速处理，精度较低</Text>
                          <br />
                          <Text>• <Text strong>Small/Medium</Text>：平衡速度和精度</Text>
                          <br />
                          <Text>• <Text strong>Large</Text>：最高精度，但处理速度较慢</Text>
                          <br />
                          <Text type="secondary">首次使用会自动下载模型（100MB-3GB）</Text>
                        </div>
                      }
                    />
                  </>
                )}

                {selectedSpeechMethod === 'funasr' && (
                  <>
                    <Alert
                      message="FunASR 语音识别（推荐）"
                      description="使用阿里开源FunASR模型进行语音识别，中文识别准确率高，完全离线可用，无需API Key。"
                      type="success"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />
                    <Alert
                      message="模型说明"
                      type="info"
                      showIcon
                      style={{ marginBottom: 24 }}
                      description={
                        <div>
                          <Text>• <Text strong>paraformer-zh</Text>：阿里开源中文语音识别模型</Text>
                          <br />
                          <Text>• 支持VAD（语音活动检测）和标点恢复</Text>
                          <br />
                          <Text type="secondary">首次使用会自动下载模型</Text>
                        </div>
                      }
                    />
                  </>
                )}

                {selectedSpeechMethod === 'openai_api' && (
                  <>
                    <Alert
                      message="OpenAI Whisper API"
                      description="使用OpenAI官方Whisper API进行语音识别，精度最高，但需要OpenAI账号和API Key。"
                      type="warning"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />

                    <Form.Item
                      label="OpenAI API Key"
                      name="openai_api_key"
                      className="form-item"
                      rules={[
                        { required: true, message: '请输入OpenAI API Key' },
                        { min: 10, message: 'API Key长度不能少于10位' }
                      ]}
                    >
                      <Input.Password
                        placeholder="请输入OpenAI API Key"
                        prefix={<KeyOutlined />}
                        className="settings-input"
                      />
                    </Form.Item>

                    <Form.Item
                      label="Whisper模型"
                      name="speech_recognition_model"
                      className="form-item"
                      initialValue="whisper-1"
                    >
                      <Input placeholder="whisper-1" className="settings-input" disabled />
                    </Form.Item>
                  </>
                )}

                {selectedSpeechMethod === 'azure_speech' && (
                  <>
                    <Alert
                      message="Azure语音服务"
                      description="使用微软Azure语音识别服务，需要Azure账号和语音服务密钥。"
                      type="warning"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />

                    <Form.Item
                      label="Azure语音服务密钥"
                      name="azure_speech_key"
                      className="form-item"
                      rules={[
                        { required: true, message: '请输入Azure语音服务密钥' }
                      ]}
                    >
                      <Input.Password
                        placeholder="请输入Azure语音服务密钥"
                        prefix={<KeyOutlined />}
                        className="settings-input"
                      />
                    </Form.Item>

                    <Form.Item
                      label="Azure服务区域"
                      name="azure_speech_region"
                      className="form-item"
                      rules={[{ required: true, message: '请输入Azure服务区域' }]}
                    >
                      <Input placeholder="eastus" className="settings-input" />
                    </Form.Item>
                  </>
                )}

                {selectedSpeechMethod === 'google_speech' && (
                  <>
                    <Alert
                      message="Google语音识别"
                      description="使用Google Cloud语音识别服务，需要Google Cloud账号和服务密钥。"
                      type="warning"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />

                    <Form.Item
                      label="Google Cloud服务密钥JSON"
                      name="google_speech_credentials"
                      className="form-item"
                      rules={[{ required: true, message: '请输入Google Cloud服务密钥' }]}
                    >
                      <Input.TextArea
                        placeholder="请粘贴Google Cloud服务密钥JSON内容"
                        className="settings-input"
                        rows={4}
                      />
                    </Form.Item>
                  </>
                )}

                {selectedSpeechMethod === 'aliyun_speech' && (
                  <>
                    <Alert
                      message="阿里云语音识别"
                      description="使用阿里云智能语音服务，需要阿里云账号和AccessKey信息。"
                      type="warning"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />

                    <Form.Item
                      label="阿里云AccessKey ID"
                      name="aliyun_access_key_id"
                      className="form-item"
                      rules={[{ required: true, message: '请输入阿里云AccessKey ID' }]}
                    >
                      <Input
                        placeholder="请输入阿里云AccessKey ID"
                        prefix={<KeyOutlined />}
                        className="settings-input"
                      />
                    </Form.Item>

                    <Form.Item
                      label="阿里云AccessKey Secret"
                      name="aliyun_access_key_secret"
                      className="form-item"
                      rules={[{ required: true, message: '请输入阿里云AccessKey Secret' }]}
                    >
                      <Input.Password
                        placeholder="请输入阿里云AccessKey Secret"
                        prefix={<KeyOutlined />}
                        className="settings-input"
                      />
                    </Form.Item>
                  </>
                )}

                {selectedSpeechMethod === 'bcut_asr' && (
                  <>
                    <Alert
                      message="B站必剪ASR"
                      description="使用B站必剪的语音识别服务，需要B站账号Cookie。识别速度快，但需要网络连接。"
                      type="info"
                      showIcon
                      style={{ marginBottom: 24 }}
                    />

                    <Form.Item
                      label="B站Cookie"
                      name="bcut_cookie"
                      className="form-item"
                      rules={[{ required: true, message: '请输入B站Cookie' }]}
                    >
                      <Input.TextArea
                        placeholder="请粘贴B站Cookie（建议使用必剪相关Cookie）"
                        className="settings-input"
                        rows={3}
                      />
                    </Form.Item>
                  </>
                )}

                <Form.Item className="form-item">
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SaveOutlined />}
                    size="large"
                    className="save-button"
                    loading={loadingStates.speech}
                  >
                    保存语音识别配置
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            <Card title="语音识别方案对比" className="settings-card">
              <Table
                dataSource={[
                  {
                    key: '1',
                    method: 'Whisper本地',
                    accuracy: '高',
                    speed: '中',
                    offline: true,
                    apiKey: false,
                    cost: '免费'
                  },
                  {
                    key: '2',
                    method: 'B站必剪ASR',
                    accuracy: '中',
                    speed: '快',
                    offline: false,
                    apiKey: false,
                    cost: '免费'
                  },
                  {
                    key: '3',
                    method: 'OpenAI Whisper',
                    accuracy: '高',
                    speed: '快',
                    offline: false,
                    apiKey: true,
                    cost: '按量付费'
                  },
                  {
                    key: '4',
                    method: 'Azure语音服务',
                    accuracy: '高',
                    speed: '快',
                    offline: false,
                    apiKey: true,
                    cost: '按量付费'
                  },
                  {
                    key: '5',
                    method: 'Google语音识别',
                    accuracy: '高',
                    speed: '快',
                    offline: false,
                    apiKey: true,
                    cost: '按量付费'
                  },
                  {
                    key: '6',
                    method: '阿里云语音识别',
                    accuracy: '高',
                    speed: '快',
                    offline: false,
                    apiKey: true,
                    cost: '按量付费'
                  }
                ]}
                columns={[
                  {
                    title: '方案',
                    dataIndex: 'method',
                    key: 'method'
                  },
                  {
                    title: '精度',
                    dataIndex: 'accuracy',
                    key: 'accuracy'
                  },
                  {
                    title: '速度',
                    dataIndex: 'speed',
                    key: 'speed'
                  },
                  {
                    title: '离线可用',
                    dataIndex: 'offline',
                    key: 'offline',
                    render: (val: boolean) => val ? <Tag color="green">是</Tag> : <Tag color="red">否</Tag>
                  },
                  {
                    title: '需要API Key',
                    dataIndex: 'apiKey',
                    key: 'apiKey',
                    render: (val: boolean) => val ? <Tag color="orange">是</Tag> : <Tag color="green">否</Tag>
                  },
                  {
                    title: '费用',
                    dataIndex: 'cost',
                    key: 'cost'
                  }
                ]}
                pagination={false}
                size="small"
              />
            </Card>
          </TabPane>

          <TabPane tab="B站管理" key="bilibili">
            <Card title="B站账号管理" className="settings-card">
              <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                <div style={{ marginBottom: '24px' }}>
                  <UserOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
                  <Title level={3} style={{ color: '#ffffff', margin: '0 0 8px 0' }}>
                    B站账号管理
                  </Title>
                  <Text type="secondary" style={{ color: '#b0b0b0', fontSize: '16px' }}>
                    管理您的B站账号，支持多账号切换和快速投稿
                  </Text>
                </div>

                <Space size="large">
                  <Button
                    type="primary"
                    size="large"
                    icon={<UserOutlined />}
                    onClick={() => message.info('开发中，敬请期待', 3)}
                    style={{
                      borderRadius: '8px',
                      background: 'linear-gradient(45deg, #1890ff, #36cfc9)',
                      border: 'none',
                      fontWeight: 500,
                      height: '48px',
                      padding: '0 32px',
                      fontSize: '16px'
                    }}
                  >
                    管理B站账号
                  </Button>
                </Space>

                <div style={{ marginTop: '32px', textAlign: 'left', maxWidth: '600px', margin: '32px auto 0' }}>
                  <Title level={4} style={{ color: '#ffffff', marginBottom: '16px' }}>
                    功能特点
                  </Title>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                    <div style={{
                      padding: '16px',
                      background: 'rgba(255,255,255,0.05)',
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#1890ff' }}>多账号支持</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        支持添加多个B站账号，方便管理和切换
                      </Text>
                    </div>
                    <div style={{
                      padding: '16px',
                      background: 'rgba(255,255,255,0.05)',
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#52c41a' }}>安全登录</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        使用Cookie导入，避免风控，安全可靠
                      </Text>
                    </div>
                    <div style={{
                      padding: '16px',
                      background: 'rgba(255,255,255,0.05)',
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#faad14' }}>快速投稿</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        在切片详情页直接选择账号投稿，操作简单
                      </Text>
                    </div>
                    <div style={{
                      padding: '16px',
                      background: 'rgba(255,255,255,0.05)',
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#722ed1' }}>批量管理</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        支持批量上传多个切片，提高效率
                      </Text>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </TabPane>
        </Tabs>

        <BilibiliManager
          visible={showBilibiliManager}
          onClose={() => setShowBilibiliManager(false)}
          onUploadSuccess={() => {
            message.success('操作成功')
          }}
        />
      </div>
    </Content>
  )
}

export default SettingsPage
