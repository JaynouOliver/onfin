"use client"

import * as React from "react"
import { Send, Plus, MessageSquare, Menu, User, Bot, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { ModeToggle } from "@/components/mode-toggle"

// Mock data for older chats
const olderChats = [
  { id: 1, title: "Portfolio Analysis", date: "2 mins ago" },
  { id: 2, title: "Market Trends Q3", date: "1 hour ago" },
  { id: 3, title: "Crypto Investment Strategy", date: "Yesterday" },
  { id: 4, title: "Retirement Planning", date: "2 days ago" },
  { id: 5, title: "Tax Optimization", date: "Last week" },
]

type Message = {
  role: "user" | "agent"
  content: string
}

const API_URL = "http://localhost:8000"
const THREAD_ID = "user-123" // Default thread ID

export default function ChatInterface() {
  const [messages, setMessages] = React.useState<Message[]>([
    { role: "agent", content: "Hello! I'm your financial agent. How can I help you today?" },
  ])
  const [inputValue, setInputValue] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(false)
  const scrollAreaRef = React.useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages change
  React.useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages, isLoading]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue("")
    setIsLoading(true)

    // Add user message immediately
    setMessages((prev) => [...prev, { role: "user", content: userMessage }])

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage,
          thread_id: THREAD_ID,
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to fetch response")
      }

      const data = await response.json()
      
      // Add agent response
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: data.response },
      ])
    } catch (error) {
      console.error("Error sending message:", error)
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Sorry, I encountered an error while processing your request. Please try again." },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const SidebarContent = () => (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between px-4 py-2">
        <h2 className="text-lg font-semibold tracking-tight">Chats</h2>
        <Button variant="ghost" size="icon" onClick={() => setMessages([])}>
          <Plus className="h-4 w-4" />
          <span className="sr-only">New Chat</span>
        </Button>
      </div>
      <div className="px-2">
        <Button className="w-full justify-start gap-2" onClick={() => setMessages([])}>
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-2 p-2">
          <p className="text-xs font-medium text-muted-foreground px-2 pb-2">Recents</p>
          {olderChats.map((chat) => (
            <Button
              key={chat.id}
              variant="ghost"
              className="w-full justify-start gap-2 text-left font-normal h-auto py-3"
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex flex-col items-start overflow-hidden">
                <span className="truncate w-full text-sm">{chat.title}</span>
                <span className="text-xs text-muted-foreground">{chat.date}</span>
              </div>
            </Button>
          ))}
        </div>
      </ScrollArea>
      <div className="p-4 mt-auto border-t">
        <div className="flex items-center gap-3">
          <Avatar>
            <AvatarImage src="/placeholder-user.jpg" />
            <AvatarFallback>ME</AvatarFallback>
          </Avatar>
          <div className="flex flex-col">
            <span className="text-sm font-medium">User</span>
            <span className="text-xs text-muted-foreground">Pro Plan</span>
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-64 flex-col border-r bg-muted/10">
        <SidebarContent />
      </aside>

      {/* Main Content */}
      <main className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <header className="flex h-14 items-center gap-4 border-b bg-background px-6">
          <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle sidebar</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SidebarContent />
            </SheetContent>
          </Sheet>
          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8">
              <AvatarImage src="/agent-avatar.png" />
              <AvatarFallback className="bg-primary text-primary-foreground">
                <Bot className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-sm font-medium">Financial Agent</h1>
              <p className="text-xs text-muted-foreground">Always active</p>
            </div>
          </div>
          <div className="ml-auto">
            <ModeToggle />
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-hidden relative">
          <ScrollArea ref={scrollAreaRef} className="h-full p-4">
            <div className="flex flex-col gap-4 max-w-3xl mx-auto pb-4">
              {messages.map((msg, index) => (
                <div
                  key={index}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "agent" && (
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback className="bg-primary text-primary-foreground">
                        <Bot className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                  )}
                  <div
                    className={`rounded-lg px-4 py-2 max-w-[80%] text-sm ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground border"
                    }`}
                  >
                    {msg.content}
                  </div>
                  {msg.role === "user" && (
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback>ME</AvatarFallback>
                    </Avatar>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3 justify-start">
                  <Avatar className="h-8 w-8 shrink-0">
                    <AvatarFallback className="bg-primary text-primary-foreground">
                      <Bot className="h-4 w-4" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="rounded-lg px-4 py-2 bg-muted text-foreground border flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-xs">Thinking...</span>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Input Area */}
        <div className="p-4 border-t bg-background">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <Input
                placeholder="Type your message..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={isLoading}
                className="flex-1"
              />
              <Button type="submit" size="icon" disabled={isLoading}>
                <Send className="h-4 w-4" />
                <span className="sr-only">Send</span>
              </Button>
            </form>
            <div className="text-center mt-2">
              <p className="text-[10px] text-muted-foreground">
                AI can make mistakes. Please review financial advice.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
