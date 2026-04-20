import React, { type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'

const REDACTION_PATTERN = /\[(EMAIL|PHONE|SSN|CREDIT_CARD|NAME)\]/g

function renderRedactionBadge(entity: string, key: string) {
  return (
    <span key={key} className="ui-badge ui-badge-alert" title={`${entity} redacted`}>
      PII Redacted
    </span>
  )
}

function decorateString(value: string): ReactNode[] {
  REDACTION_PATTERN.lastIndex = 0
  if (!REDACTION_PATTERN.test(value)) {
    return [value]
  }

  REDACTION_PATTERN.lastIndex = 0
  const parts = value.split(REDACTION_PATTERN)

  return parts.reduce<ReactNode[]>((nodes, part, index) => {
    if (!part) return nodes
    if (index % 2 === 1) {
      nodes.push(renderRedactionBadge(part, `${part}-${index}`))
      return nodes
    }
    nodes.push(part)
    return nodes
  }, [])
}

function decorateNode(node: ReactNode): ReactNode {
  if (typeof node === 'string') {
    return decorateString(node)
  }

  if (Array.isArray(node)) {
    return node.flatMap((child) => {
      const decorated = decorateNode(child)
      return Array.isArray(decorated) ? decorated : [decorated]
    })
  }

  if (React.isValidElement<{ children?: ReactNode }>(node) && node.props.children !== undefined) {
    return React.cloneElement(node, undefined, decorateNode(node.props.children))
  }

  return node
}

function textBlock(Tag: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'blockquote' | 'li') {
  return function TextBlock({ children }: { children?: ReactNode }) {
    return <Tag>{decorateNode(children)}</Tag>
  }
}

export default function RichMarkdown({ content, className = '' }: { content: string; className?: string }) {
  return (
    <ReactMarkdown
      className={['markdown-body', className].filter(Boolean).join(' ')}
      components={{
        h1: textBlock('h1'),
        h2: textBlock('h2'),
        h3: textBlock('h3'),
        h4: textBlock('h4'),
        p: textBlock('p'),
        blockquote: textBlock('blockquote'),
        li: textBlock('li'),
        code({ inline, children, className: codeClassName, ...props }: any) {
          if (inline) {
            return (
              <code className="markdown-inline-code" {...props}>
                {decorateNode(children)}
              </code>
            )
          }

          return (
            <code className={codeClassName} {...props}>
              {decorateNode(children)}
            </code>
          )
        },
        pre({ children }: { children?: ReactNode }) {
          return <pre className="markdown-pre">{decorateNode(children)}</pre>
        },
        strong({ children }: { children?: ReactNode }) {
          return <strong>{decorateNode(children)}</strong>
        },
        em({ children }: { children?: ReactNode }) {
          return <em>{decorateNode(children)}</em>
        },
      }}
    >
      {content || ''}
    </ReactMarkdown>
  )
}
