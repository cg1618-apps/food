// Frontend: the image library, /edit/images - every uploaded picture, what
// uses each one, and delete for the ones nothing uses.
//
// media's admin Images page, cut to what food has: no "missing on this
// machine" and no filename search, because food's images do not travel
// between machines through a backup and have no names worth searching.
//
// Delete is offered only for an unused image, as in media: removing a picture
// from a recipe is done on that recipe's form, where you can see what you are
// taking it from, not as a blanket "delete anyway" here. The server checks
// again - it answers 409 with the owners if the picture was attached since the
// page loaded - and the tile then shows those owners instead.
//
// The list answers summaries with an `attachment_count`; who the owners are is
// on each image's detail, read only for the tiles that have any. The unused
// filter and the page are in the URL (`?unused=1&page=2`), so Back works and a
// filtered view can be reloaded.
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ConfirmModal from '../../components/modals/ConfirmModal'
import { Button, Chip, LinkButton } from '../../components/ui/primitives'
import { Empty, ErrorNote, Loading } from '../../components/ui/states'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { formatBytes, ownerHref, ownerKind } from '../../lib/imageOwners'

export const PAGE_SIZE = 30

export default function ImageLibrary() {
  const [searchParams, setSearchParams] = useSearchParams()
  const unused = searchParams.get('unused') === '1'
  const page = Math.max(0, Number(searchParams.get('page') || 1) - 1) || 0

  // One more than a page, so "is there a next page" is known without a total.
  const list = useApiQuery(endpoints.images.list(), {
    unused: unused ? 'true' : undefined,
    limit: PAGE_SIZE + 1,
    offset: page * PAGE_SIZE,
  })
  const rows = (list.data ?? []).slice(0, PAGE_SIZE)
  const hasNext = (list.data?.length ?? 0) > PAGE_SIZE

  function go({ unused: nextUnused = unused, page: nextPage = 0 }) {
    const next = new URLSearchParams()
    if (nextUnused) next.set('unused', '1')
    if (nextPage > 0) next.set('page', String(nextPage + 1))
    setSearchParams(next)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">圖片</h1>
        <LinkButton to="/edit/settings" size="sm">
          回到設定
        </LinkButton>
      </div>
      <p className="text-sm text-text-muted">
        上傳過的每一張圖，和用到它的食譜、食材、筆記。沒有地方使用的圖才能在這裡刪除；要拿掉用著的圖，到那個項目的表單裡移除。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" aria-pressed={unused} onClick={() => go({ unused: !unused })}>
          <Chip tone={unused ? 'brand' : 'neutral'}>只看未使用</Chip>
        </button>
      </div>

      {list.isPending ? <Loading /> : null}
      {list.isError ? <ErrorNote error={list.error} /> : null}
      {list.isSuccess && rows.length === 0 ? (
        page > 0 ? (
          <Empty action={<Button onClick={() => go({ page: 0 })}>回到第一頁</Button>}>這一頁沒有圖片。</Empty>
        ) : unused ? (
          <Empty action={<Button onClick={() => go({ unused: false })}>看全部</Button>}>
            沒有未使用的圖片。
          </Empty>
        ) : (
          <Empty>圖庫是空的。圖片在食譜、食材和筆記的表單裡上傳。</Empty>
        )
      ) : null}

      {rows.length ? (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {rows.map((image) => (
            <ImageTile key={image.id} image={image} />
          ))}
        </ul>
      ) : null}

      {page > 0 || hasNext ? (
        <nav aria-label="分頁" className="flex items-center justify-between text-sm text-text-muted">
          <Button size="sm" disabled={page === 0} onClick={() => go({ page: page - 1 })}>
            上一頁
          </Button>
          <span>第 {page + 1} 頁</span>
          <Button size="sm" disabled={!hasNext} onClick={() => go({ page: page + 1 })}>
            下一頁
          </Button>
        </nav>
      ) : null}
    </div>
  )
}

function ImageTile({ image }) {
  const remove = useApiMutation({ method: 'DELETE', invalidate: [endpoints.images.list()] })
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  // Owners a refused delete answered with: the picture was attached after the
  // list was read, so the count on screen is stale and these are the truth.
  const [refusedOwners, setRefusedOwners] = useState(null)

  const attached = image.attachment_count > 0 || refusedOwners !== null
  const name = image.original_filename || `圖片 ${image.id}`

  async function confirmDelete() {
    setError(null)
    try {
      await remove.mutateAsync({ url: endpoints.images.remove(image.id) })
    } catch (caught) {
      if (caught?.status === 409 && Array.isArray(caught.body?.owners)) {
        setRefusedOwners(caught.body.owners)
        setError('它剛被用上了，不能刪；先到下面的項目裡移除。')
      } else {
        setError(caught?.message || '刪除失敗。')
      }
    } finally {
      setConfirming(false)
    }
  }

  return (
    <li aria-label={name} className="flex flex-col gap-2 rounded-md border border-border bg-surface p-2">
      <a
        href={image.url}
        target="_blank"
        rel="noreferrer"
        className="block aspect-square overflow-hidden rounded-sm border border-border bg-surface-2"
      >
        <img
          loading="lazy"
          src={image.thumb_url}
          alt={name}
          className="h-full w-full object-cover"
          // A library picture: its focus belongs to each owner it is attached
          // to, not to the file, so the thumbnail stays centred.
          data-focus="none"
        />
      </a>

      <div className="min-w-0 space-y-0.5 text-xs text-text-muted">
        <p className="truncate" title={name}>
          {name}
        </p>
        <p className="text-text-faint">
          {image.width}×{image.height} · {formatBytes(image.byte_size)}
        </p>
      </div>

      {attached ? (
        <Owners imageId={image.id} known={refusedOwners} />
      ) : (
        <>
          <Chip className="self-start">未使用</Chip>
          <Button kind="danger" size="sm" onClick={() => setConfirming(true)} disabled={remove.isPending}>
            刪除
          </Button>
        </>
      )}

      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}

      {confirming ? (
        <ConfirmModal
          title="刪除這張圖片？"
          confirmLabel="刪除"
          danger
          busy={remove.isPending}
          onConfirm={confirmDelete}
          onCancel={() => setConfirming(false)}
        >
          「{name}」沒有任何地方使用；刪除會把檔案一起移除，無法復原。
        </ConfirmModal>
      ) : null}
    </li>
  )
}

// Who uses an image, as links. `known` is a refused delete's owner list; with
// none, the image's detail is read for them.
function Owners({ imageId, known }) {
  const detail = useApiQuery(endpoints.images.detail(imageId), null, { enabled: known === null })
  const owners = known ?? detail.data?.owners

  if (!owners) {
    if (detail.isError) return <ErrorNote error={detail.error} />
    return <p className="text-xs text-text-faint">載入用途…</p>
  }
  return (
    <ul className="space-y-0.5 text-xs" aria-label="用在">
      {owners.map((owner) => (
        <li key={`${owner.type}-${owner.id}`} className="truncate">
          <span className="text-text-faint">{ownerKind(owner.type)} · </span>
          {ownerHref(owner) ? (
            <Link to={ownerHref(owner)} className="text-brand hover:underline">
              {owner.display_name}
            </Link>
          ) : (
            owner.display_name
          )}
        </li>
      ))}
    </ul>
  )
}
