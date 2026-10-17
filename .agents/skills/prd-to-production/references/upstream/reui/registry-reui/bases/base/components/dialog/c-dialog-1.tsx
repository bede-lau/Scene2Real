"use client"

import { useId, useState, type FormEvent } from "react"

import { Button } from "@/registry/bases/base/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/registry/bases/base/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/registry/bases/base/ui/field"
import { Input } from "@/registry/bases/base/ui/input"

export default function Pattern() {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [profile, setProfile] = useState({
    name: "Pedro Duarte",
    username: "@peduarte",
  })

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    setProfile({
      name: String(formData.get("name")),
      username: String(formData.get("username")),
    })
    setOpen(false)
  }

  return (
    <div className="flex items-center justify-center">
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger render={<Button variant="outline" />}>
          Basic Dialog
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit profile</DialogTitle>
            <DialogDescription>
              Make changes to your profile here. Click save when you&apos;re
              done. Your profile will be updated immediately.
            </DialogDescription>
          </DialogHeader>
          {/* The form sits inside the portaled content so Save can submit it. */}
          <form onSubmit={handleSubmit} className="contents">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor={`${id}-name`}>Name</FieldLabel>
                <Input
                  id={`${id}-name`}
                  name="name"
                  defaultValue={profile.name}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${id}-username`}>Username</FieldLabel>
                <Input
                  id={`${id}-username`}
                  name="username"
                  defaultValue={profile.username}
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <DialogClose render={<Button variant="outline" />}>
                Cancel
              </DialogClose>
              <Button type="submit">Save changes</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
